"""Synthetic estimator comparison, not a production uplift test."""
import random,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/gateway'))
from app.routing.bayesian_feedback import estimate_feedback,published_prior

def run(trials=3000):
 rng=random.Random(20261007);rows=[]
 for scenario in ['neutral','similar_population','opposite_population']:
  for n in [30,60,300]:
   raw_error=bayes_error=0.
   for _ in range(trials):
    p=rng.random();positive=sum(rng.random()<p for _ in range(n))
    if scenario=='neutral':mean,strength=.5,2.
    else:
     population_p=p if scenario=='similar_population' else 1-p
     other_positive=sum(rng.random()<population_p for _ in range(100))
     mean,strength=published_prior(other_positive,100)
    posterior=estimate_feedback(positive,n,mean,strength)['posteriorMean']
    raw_error+=(positive/n-p)**2;bayes_error+=(posterior-p)**2
   rows.append({'scenario':scenario,'samples':n,'trials':trials,'rawMSE':raw_error/trials,'bayesianMSE':bayes_error/trials,'relativeReductionPct':(1-bayes_error/raw_error)*100})
 return {'seed':20261007,'synthetic':True,'metric':'satisfaction probability mean squared error','rows':rows}
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
