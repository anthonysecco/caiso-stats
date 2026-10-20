"""Base entity for CAISO Stats."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, OUTLOOK_URL
from .coordinator import CaisoCoordinator


class CaisoEntity(CoordinatorEntity[CaisoCoordinator]):
    """One entity on the shared "CAISO" service device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: CaisoCoordinator, description: EntityDescription) -> None:
        """Bind the description and device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="CAISO",
            manufacturer="California ISO",
            model="Today's Outlook",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=OUTLOOK_URL,
        )
