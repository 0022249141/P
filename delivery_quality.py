# delivery_quality.py — کیفیت تحویل حرکت
import pandas as pd
import numpy as np

def evaluate_delivery(df, bos_col='bos_bull', direction='bull'):
    df = df.copy()
    n = len(df)
    df['delivery_score'] = 0
    df['displacement_ok'] = False
    df['low_overlap_ok'] = False
    df['follow_through_ok'] = False
    df['clean_rejection_ok'] = False

    for i in range(1, n - 3):
        if not df[bos_col].iloc[i]:
            continue
        score = 0
        body = abs(df['close'].iloc[i] - df['open'].iloc[i])
        rng = df['high'].iloc[i] - df['low'].iloc[i]

        # 1. Displacement
        if rng > 0 and (body / rng) > 0.6:
            df.loc[df.index[i], 'displacement_ok'] = True
            score += 1

        # 2. Low Overlap (3 کندل بعد)
        overlaps = []
        for j in range(i+1, min(i+4, n)):
            prev_h, prev_l = df['high'].iloc[j-1], df['low'].iloc[j-1]
            curr_h, curr_l = df['high'].iloc[j], df['low'].iloc[j]
            overlap = max(0, min(prev_h, curr_h) - max(prev_l, curr_l))
            prev_rng = prev_h - prev_l
            if prev_rng > 0:
                overlaps.append(overlap / prev_rng)
        if overlaps and np.mean(overlaps) < 0.3:
            df.loc[df.index[i], 'low_overlap_ok'] = True
            score += 1

        # 3. Follow-Through
        if direction == 'bull':
            follow = all(df['close'].iloc[i+j] > df['close'].iloc[i] for j in range(1, 4) if i+j < n)
        else:
            follow = all(df['close'].iloc[i+j] < df['close'].iloc[i] for j in range(1, 4) if i+j < n)
        if follow:
            df.loc[df.index[i], 'follow_through_ok'] = True
            score += 1

        # 4. Clean Rejection
        if direction == 'bull':
            if df['high'].iloc[i] > df['high'].iloc[i-1] and df['close'].iloc[i] < df['high'].iloc[i-1]:
                df.loc[df.index[i], 'clean_rejection_ok'] = True
                score += 1
        else:
            if df['low'].iloc[i] < df['low'].iloc[i-1] and df['close'].iloc[i] > df['low'].iloc[i-1]:
                df.loc[df.index[i], 'clean_rejection_ok'] = True
                score += 1

        df.loc[df.index[i], 'delivery_score'] = score
    return df