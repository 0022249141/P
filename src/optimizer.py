import pandas as pd
import numpy as np
from itertools import product
import random
from scoring_engine import ScoringEngine
from execution_logic import ExecutionLogic

class Optimizer:
    def __init__(self, market_engine, struct_engine, liq, disp, zone, vp, ice):
        self.market_engine = market_engine
        self.struct_engine = struct_engine
        self.liq, self.disp, self.zone = liq, disp, zone
        self.vp, self.ice = vp, ice
        self.best_score = -np.inf
        self.best_weights = None

    def evaluate_weights(self, w_sweep, w_disp, w_zone, w_htf, w_vpoc=0.05, w_iceberg=0.05):
        """
        اجرای ScoringEngine با وزن‌های مشخص و محاسبه Expectancy ساده.
        """
        weights = {
            'sweep': w_sweep,
            'disp': w_disp,
            'zone': w_zone,
            'htf': w_htf,
            'vpoc': w_vpoc,
            'iceberg': w_iceberg
        }
        scorer = ScoringEngine(self.liq, self.disp, self.zone, self.vp, self.ice, htf_bias=0.6, weights=weights)
        executor = ExecutionLogic(scorer, self.market_engine, self.struct_engine)  # حالا struct دارد
        signals = executor.generate_signals(min_setup_score=70)

        if signals.empty:
            return -1e9

        wins = 0
        losses = 0
        for _, sig in signals.iterrows():
            ts = sig['timestamp']
            idx = self.market_engine.df.index[self.market_engine.df['timestamp'] == ts]
            if len(idx) == 0:
                continue
            i = idx[0]
            future = self.market_engine.df.iloc[i+1 : min(i+20, len(self.market_engine.df))]
            if len(future) < 2:
                continue

            if sig['direction'] == 'BUY':
                if (future['high'] >= sig['tp_price']).any():
                    wins += 1
                elif (future['low'] <= sig['sl_price']).any():
                    losses += 1
            else:  # SELL
                if (future['low'] <= sig['tp_price']).any():
                    wins += 1
                elif (future['high'] >= sig['sl_price']).any():
                    losses += 1

        total = wins + losses
        if total == 0:
            return -1e9
        wr = wins / total
        expectancy = wr * 2 - (1 - wr) * 1  # 2:1 reward
        return expectancy

    def grid_search(self, param_grid):
        best = {'score': -np.inf, 'weights': None}
        keys = list(param_grid.keys())
        combinations = list(product(*param_grid.values()))
        for combo in combinations:
            w = dict(zip(keys, combo))
            score = self.evaluate_weights(**w)
            if score > best['score']:
                best = {'score': score, 'weights': w}
        self.best_weights = best['weights']
        self.best_score = best['score']
        return best

    def genetic_algorithm(self, pop_size=20, generations=10, mutation_rate=0.1):
        # Initial random population
        population = []
        for _ in range(pop_size):
            ind = {
                'sweep': random.uniform(0, 1),
                'disp': random.uniform(0, 1),
                'zone': random.uniform(0, 1),
                'htf': random.uniform(0, 1),
                'vpoc': random.uniform(0, 0.2),
                'iceberg': random.uniform(0, 0.2)
            }
            total = sum(ind.values())
            ind = {k: v/total for k, v in ind.items()}
            population.append(ind)

        for gen in range(generations):
            scores = [self.evaluate_weights(**ind) for ind in population]
            sorted_pop = [ind for _, ind in sorted(zip(scores, population), key=lambda x: x[0], reverse=True)]
            new_pop = sorted_pop[:4]  # elites
            while len(new_pop) < pop_size:
                parent1, parent2 = random.sample(sorted_pop[:10], 2)
                child = {}
                for k in parent1:
                    child[k] = (parent1[k] + parent2[k]) / 2
                    if random.random() < mutation_rate:
                        child[k] += random.uniform(-0.1, 0.1)
                        child[k] = max(0, child[k])
                total = sum(child.values())
                child = {k: v/total for k, v in child.items()}
                new_pop.append(child)
            population = new_pop

        final_scores = [self.evaluate_weights(**ind) for ind in population]
        best_idx = np.argmax(final_scores)
        self.best_weights = population[best_idx]
        self.best_score = final_scores[best_idx]
        return self.best_weights, self.best_score