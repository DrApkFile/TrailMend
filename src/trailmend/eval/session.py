from trailmend.graph.client import HydraClient
from trailmend.settings import load_settings


def client_from_settings() -> HydraClient:
    settings = load_settings()
    return HydraClient(
        str(settings.hydra_url),
        settings.hydra_token.get_secret_value(),
        settings.hydra_graph_id,
        settings.hydra_cell_id,
        settings.hydra_timeout_s,
    )
