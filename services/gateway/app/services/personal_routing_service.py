from app.routing.explainable_router import DEFAULT_WEIGHTS

PREFERENCE_MODES = {'balanced', 'quality', 'cost', 'latency'}
def preference_weights(mode):
    weights = dict(DEFAULT_WEIGHTS)
    if mode in {'quality', 'cost', 'latency'}:
        weights[mode] += .30
    return weights


def feedback_for_user(shared, personal, model_id, task_type):
    own = personal.get((model_id, task_type)) or personal.get((model_id, 'general'))
    if own and own.sample_count >= 30:
        return own, '个人反馈'
    return shared.get((model_id, task_type)) or shared.get((model_id, 'general')), '共享反馈'


async def other_users_priors(db, user_id, model_ids, task_types):
    from sqlalchemy import select, func
    from app.models.answer_feedback import PersonalSatisfactionProfile as P
    from app.routing.bayesian_feedback import published_prior
    rows = (await db.execute(select(P.model_id, P.task_type, func.sum(P.positive_count), func.sum(P.sample_count))
        .where(P.user_id != user_id, P.model_id.in_(model_ids), P.task_type.in_(task_types), P.sample_count >= 30)
        .group_by(P.model_id, P.task_type))).all()
    return {(mid, task):published_prior(int(positive), int(samples)) for mid,task,positive,samples in rows}
