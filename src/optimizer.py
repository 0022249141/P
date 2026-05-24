"""Portfolio optimizer for weight selection."""
import pandas as pd
import numpy as np
from itertools import product
import random


class Optimizer:
    """Optimize engine weights using grid or genetic algorithm."""

    def __init__(self, market_engine, struct_engine, liq, disp,
                 zone, vp, ice):
        """Initialize optimizer."""
        self.market_engine = market_engine
        self.struct_engine = struct_engine
        self.liq, self.disp, self.zone = liq, disp, zone
        self.vp, self.ice = vp, ice
        self.best_score = -np.inf
        self.best_weights = None

    def evaluate_weights(self, w_sweep, w_disp, w_zone, w_htf,
                        w_vpoc=0.05, w_iceberg=0.05):
        """اجرای ScoringEngine با وزن‌های مشخص.

        محاسبه Expectancy ساده.
        """
        weights = {
            'sweep': w_sweep,
            'disp': w_disp,
            'zone': w_zone,
            'htf': w_htf,
            'vpoc': w_vpoc,
            'iceberg': w_iceberg
        }
        # Avoid circular import
        try:
            from scoring_engine import ScoringEngine
            from execution_logic import ExecutionLogic
            scorer = ScoringEngine(
                self.liq, self.disp, self.zone, self.vp, self.ice,
                htf_bias=0.6, weights=weights
            )
            executor = ExecutionLogic(
                scorer, self.market_engine, self.struct_engine
            )
            signals = executor.generate_signals(min_setup_score=70)
        except ImportError:
            return -1e9

        if signals.empty:
            return -1e9

        wins = 0
        losses = 0
        for _, sig in signals.iterrows():
            ts = sig['timestamp']
            idx = self.market_engine.df.index[
                self.market_engine.df['timestamp'] == ts
            ]
            if len(idx) == 0:
                continue
            i = idx[0]
            future = self.market_engine.df.iloc[
                i+1 : min(i+20, len(self.market_engine.df))
            ]
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
        """Grid search optimization."""
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

    def genetic_algorithm(self, pop_size=20, generations=10,
                         mutation_rate=0.1):
        """Genetic algorithm optimization."""
        # Initial random population
        population = []
        for _ in range(pop_size):
            ind = {
                'w_sweep': random.random(),
                'w_disp': random.random(),
                'w_zone': random.random(),
                'w_htf': random.random()
            }
            ind['score'] = self.evaluate_weights(**ind)
            population.append(ind)

        for gen in range(generations):
            population.sort(key=lambda x: x['score'], reverse=True)
            print(f"Generation {gen}: Best = {population[0]['score']:.4f}")

            # Keep top half
            elite = population[:pop_size//2]

            # Crossover and mutation
            new_pop = elite[:]
            while len(new_pop) < pop_size:
                parent = random.choice(elite)
                child = parent.copy()
                if random.random() < mutation_rate:
                    key = random.choice(list(child.keys()))
                    if key != 'score':
                        child[key] += (random.random() - 0.5) * 0.1
                        child[key] = max(0, min(1, child[key]))
                child['score'] = self.evaluate_weights(
                    w_sweep=child['w_sweep'],
                    w_disp=child['w_disp'],
                    w_zone=child['w_zone'],
                    w_htf=child['w_htf']
                )
                new_pop.append(child)
            population = new_pop

        population.sort(key=lambda x: x['score'], reverse=True)
        self.best_weights = population[0]
        self.best_score = population[0]['score']
        return population[0]
