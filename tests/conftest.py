from hypothesis import HealthCheck, settings

settings.register_profile("trailmend", suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("trailmend")
