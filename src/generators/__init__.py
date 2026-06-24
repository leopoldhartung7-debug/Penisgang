from .discord import DiscordGenerator
from .steam import SteamGenerator
from .rockstar import RockstarGenerator

REGISTRY = {
    "discord": DiscordGenerator,
    "steam": SteamGenerator,
    "rockstar": RockstarGenerator,
}
