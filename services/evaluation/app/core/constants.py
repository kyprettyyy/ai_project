"""
缓存常量
"""


class CacheConstant:
    """
    缓存常量
    """

    MODEL_PRICING_CACHE_NAME = "modelPricing"

    MODEL_PRICING_KEY_PREFIX = "evaluation:model:pricing:"

    MODEL_PRICING_TTL_HOURS = 24

    USER_DAILY_COST_KEY_PREFIX = "evaluation:user:cost:daily:"

    USER_MONTHLY_COST_KEY_PREFIX = "evaluation:user:cost:monthly:"

    USER_DAILY_COST_TTL_HOURS = 25

    USER_MONTHLY_COST_TTL_DAYS = 32

    STATISTICS_COST_KEY_PREFIX = "evaluation:statistics:cost:"

    STATISTICS_USAGE_KEY_PREFIX = "evaluation:statistics:usage:"

    STATISTICS_PERFORMANCE_KEY_PREFIX = "evaluation:statistics:performance:"

    STATISTICS_TTL_MINUTES = 5
