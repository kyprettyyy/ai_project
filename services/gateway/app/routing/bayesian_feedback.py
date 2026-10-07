"""Beta-Bernoulli satisfaction estimate, not an accuracy estimate.

Only published batches enter routing. Other users' published evidence supplies a
bounded empirical prior. Posterior-mean selection is deterministic (no exploration).
"""
from math import sqrt, isfinite

ALGORITHM_VERSION = 'beta-bernoulli-v1'
MIN_BATCH = 30
MAX_FEEDBACK_WEIGHT = .20
CONFIDENCE_SCALE = 30
MAX_PRIOR_STRENGTH = 20

def published_prior(positive: int, samples: int) -> tuple[float, float]:
    if samples < 0 or positive < 0 or positive > samples:
        raise ValueError('Invalid prior vote counts')
    if samples == 0:
        return .5, 2.
    return (positive + 1)/(samples + 2), min(MAX_PRIOR_STRENGTH, samples + 2)

def estimate_feedback(positive: float, samples: int, prior_mean: float = .5,
                      prior_strength: float = 2.) -> dict:
    if samples < 0 or not isfinite(positive) or not 0 <= positive <= samples:
        raise ValueError('Invalid feedback counts')
    if not isfinite(prior_mean) or not 0 < prior_mean < 1 or not isfinite(prior_strength) or prior_strength <= 0:
        raise ValueError('Invalid Beta prior')
    original_prior = {'mean':prior_mean, 'strength':prior_strength}
    prior_conflict = False
    if samples >= MIN_BATCH and prior_strength > 2:
        smoothed = (positive+1)/(samples+2)
        threshold = max(.15, 2*sqrt(smoothed*(1-smoothed)/(samples+3)))
        if abs(positive/samples-prior_mean) > threshold:
            prior_mean, prior_strength = .5, 2.
            prior_conflict = True
    alpha = prior_mean * prior_strength + positive
    beta = (1-prior_mean) * prior_strength + samples-positive
    total = alpha+beta
    confidence = samples/(samples+CONFIDENCE_SCALE)
    return {'algorithm':ALGORITHM_VERSION, 'samples':samples,
            'rawRate':positive/samples if samples else None,
            'priorMean':prior_mean, 'priorStrength':prior_strength,
            'originalPrior':original_prior, 'priorConflict':prior_conflict,
            'posteriorMean':alpha/total,
            'posteriorStdDev':sqrt(alpha*beta/(total*total*(total+1))),
            'confidence':confidence,
            'routingWeight':MAX_FEEDBACK_WEIGHT*confidence if samples >= MIN_BATCH else 0.}
