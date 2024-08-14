"""provides the Iris light platform."""

import logging
import math
from typing import Any

from aiohttp import ClientResponse, ClientSession

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.scaling import scale_to_ranged_value

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Iris light platform."""
    _LOGGER.debug(
        {
            "hass": hass,
            "config_entry": config_entry,
            "async_add_entities": async_add_entities,
        }
    )
    light = Light(hass, config_entry)
    async_add_entities([light])
    await light.get_update()


class Light(LightEntity):
    """Representation of a light."""

    # _attr_has_entity_name = True

    _brightness = 10
    _max_blightness = 10
    BRIGHTNESS_SCALE = (1, 10)
    _color_temp = 6
    _max_color_temp = 11
    COLOR_TEMP_SCALE = (1, 11)
    _state: int = 2

    _host: str
    _session: ClientSession
    _url: str

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize an Iris Light."""
        # self._attr_unique_id = "light_" + config_entry.data[CONF_HOST]
        # self._attr_name = config_entry.title
        self._host = config_entry.data[CONF_HOST]
        self._session = async_get_clientsession(hass)
        self._url = f"http://{self._host}/api/iris-lights/"

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return ColorMode.COLOR_TEMP

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {ColorMode.COLOR_TEMP}

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._host

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 1..255."""
        if(self._state == 1):
            return 1
        return self._value_to_brightness(self.BRIGHTNESS_SCALE, self._brightness)

    @property
    def color_temp(self) -> int:
        """Return the CT color value in mireds."""
        return math.ceil(
            scale_to_ranged_value(self.COLOR_TEMP_SCALE, (155, 500), self._color_temp)
        )

    @property
    def is_on(self) -> bool:
        """Return the on/off state of the light."""
        return self._state != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug(kwargs)
        if "brightness" in kwargs and kwargs["brightness"] == 1:
            await self._post_data("night")
            return
        await self._post_data("on")
        if "brightness" in kwargs:
            self._brightness = math.ceil(
                self._brightness_to_value(self.BRIGHTNESS_SCALE, kwargs["brightness"])
            )
            await self._post_data("bright", self._brightness)
        if "color_temp" in kwargs:
            self._color_temp = math.ceil(
                scale_to_ranged_value(
                    (155, 500), self.COLOR_TEMP_SCALE, kwargs["color_temp"]
                )
            )
            await self._post_data("color-temp", self._color_temp)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._post_data("off")

    async def _post_data(self, url, value=None) -> ClientResponse:
        """Fetch the latest state of the light."""
        _LOGGER.debug({"url": url, "value": value})
        return await self._session.post(
            self._url + url,
            json={"value": value},
        )

    async def async_update(self) -> None:
        """Fetch the latest state of the light."""
        _LOGGER.debug("fetching update")
        await self.get_update()

    async def get_update(self) -> None:
        """Retrieve the latest update from the specified URL and set the update."""
        response = await self._session.get(self._url)
        await self._set_update(response)

    async def _set_update(self, response) -> None:
        """Set the latest update from the specified URL."""
        data = await response.json()
        self._brightness = data["brightness"]
        self._color_temp = data["color_temp"]
        self._state = data["state"]
        self.async_write_ha_state()

    def _value_to_brightness(
        self, low_high_range: tuple[float, float], value: float
    ) -> int:
        return min(
            255,
            max(1, round(scale_to_ranged_value(low_high_range, (5, 255), value))),
        )

    def _brightness_to_value(
        self, low_high_range: tuple[float, float], brightness: int
    ) -> float:
        return scale_to_ranged_value((5, 255), low_high_range, brightness)
