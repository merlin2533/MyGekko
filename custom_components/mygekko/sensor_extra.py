"""Sensors for energy managers, e-mobility and heating circuits."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.const import EntityCategory
from homeassistant.const import UnitOfEnergy
from homeassistant.const import UnitOfPower
from homeassistant.const import UnitOfTemperature

from .entity import MyGekkoEntity


@dataclass(frozen=True, kw_only=True)
class MyGekkoPropertySensorDescription(SensorEntityDescription):
    """Sensor description reading a python property of the MyGekko device."""

    attr: str


def _sensor(group, attr, name, device_class, state_class, unit, category=None):
    return MyGekkoPropertySensorDescription(
        key=attr,
        attr=attr,
        name=name,
        translation_key=f"mygekko_{group}_{attr}",
        device_class=device_class,
        state_class=state_class,
        native_unit_of_measurement=unit,
        entity_category=category,
    )


def _power(group, attr, name, unit=UnitOfPower.WATT, category=None):
    return _sensor(
        group, attr, name, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, unit, category
    )


def _energy(group, attr, name, unit=UnitOfEnergy.WATT_HOUR):
    return _sensor(
        group, attr, name, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, unit
    )


def _temperature(group, attr, name):
    return _sensor(
        group,
        attr,
        name,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        UnitOfTemperature.CELSIUS,
    )


def _percent(group, attr, name, device_class=None):
    return _sensor(
        group, attr, name, device_class, SensorStateClass.MEASUREMENT, PERCENTAGE
    )


_EM = "energymanager"
ENERGY_MANAGER_SENSORS = (
    _power(_EM, "grid_meter_power", "Grid Power"),
    _power(_EM, "power_exported_to_grid", "Power Exported To Grid"),
    _power(_EM, "power_from_solar_panels", "Solar Power"),
    _power(_EM, "power_from_battery", "Battery Power"),
    _power(_EM, "power_charging_battery", "Battery Charging Power"),
    _power(_EM, "home_power_consumption", "Home Power Consumption"),
    _energy(_EM, "daily_energy_imported_from_grid", "Daily Energy Imported From Grid"),
    _energy(_EM, "daily_energy_exported_to_grid", "Daily Energy Exported To Grid"),
    _energy(_EM, "daily_energy_from_solar_panels", "Daily Solar Energy"),
    _energy(_EM, "daily_energy_from_battery", "Daily Energy From Battery"),
    _energy(_EM, "daily_energy_charging_battery", "Daily Energy Charging Battery"),
    _energy(_EM, "daily_home_energy_consumption", "Daily Home Energy Consumption"),
    _percent(_EM, "battery_soc", "Battery Charge", SensorDeviceClass.BATTERY),
)

_EV = "emobil"
EMOBIL_SENSORS = (
    _power(_EV, "current_charging_power", "Charging Power", UnitOfPower.KILO_WATT),
    _power(
        _EV, "maximum_charging_power", "Maximum Charging Power", UnitOfPower.KILO_WATT,
        EntityCategory.DIAGNOSTIC,
    ),
    _power(
        _EV, "charging_power_setpoint", "Charging Power Setpoint", UnitOfPower.KILO_WATT,
        EntityCategory.DIAGNOSTIC,
    ),
    _energy(_EV, "current_charging_energy", "Charged Energy", UnitOfEnergy.KILO_WATT_HOUR),
)

_HC = "heatingcircuit"
HEATING_CIRCUIT_SENSORS = (
    _temperature(_HC, "flow_temperature", "Flow Temperature"),
    _temperature(_HC, "return_flow_temperature", "Return Flow Temperature"),
    _temperature(_HC, "flow_temperature_setpoint", "Flow Temperature Setpoint"),
    _temperature(_HC, "dew_point", "Dew Point"),
    _percent(_HC, "pump_working_level", "Pump Level"),
    _percent(_HC, "valve_opening_level", "Valve Opening"),
)

# German names of the sensors above, used to generate translations/de.json
GERMAN_NAMES = {
    "grid_meter_power": "Netzleistung",
    "power_exported_to_grid": "Einspeisung ins Netz",
    "power_from_solar_panels": "Solarleistung",
    "power_from_battery": "Batterieleistung",
    "power_charging_battery": "Batterie-Ladeleistung",
    "home_power_consumption": "Hausverbrauch",
    "daily_energy_imported_from_grid": "Netzbezug heute",
    "daily_energy_exported_to_grid": "Einspeisung heute",
    "daily_energy_from_solar_panels": "Solarertrag heute",
    "daily_energy_from_battery": "Energie aus Batterie heute",
    "daily_energy_charging_battery": "Batterie-Ladeenergie heute",
    "daily_home_energy_consumption": "Hausverbrauch heute",
    "battery_soc": "Batterieladung",
    "current_charging_power": "Ladeleistung",
    "maximum_charging_power": "Maximale Ladeleistung",
    "charging_power_setpoint": "Ladeleistung Sollwert",
    "current_charging_energy": "Geladene Energie",
    "flow_temperature": "Vorlauftemperatur",
    "return_flow_temperature": "Rücklauftemperatur",
    "flow_temperature_setpoint": "Vorlauftemperatur Soll",
    "dew_point": "Taupunkt",
    "pump_working_level": "Pumpenleistung",
    "valve_opening_level": "Ventilöffnung",
}


class MyGekkoPropertySensor(MyGekkoEntity, SensorEntity):
    """Generic sensor reading one property of a MyGekko device."""

    entity_description: MyGekkoPropertySensorDescription

    def __init__(self, coordinator, entity, prefix, description):
        """Initialize the sensor."""
        super().__init__(coordinator, entity, prefix, f"_{description.key}")
        self._entity = entity
        self.entity_description = description

    @property
    def native_value(self):
        """Return the value, None when not (yet) available."""
        return getattr(self._entity, self.entity_description.attr, None)


def build_extra_sensors(coordinator):
    """Create sensors for energy managers, e-mobility and heating circuits."""
    api = coordinator.api
    groups = (
        (api.get_energy_managers(), "energy_manager", ENERGY_MANAGER_SENSORS),
        (api.get_emobils(), "emobil", EMOBIL_SENSORS),
        (api.get_heating_circuits(), "heating_circuit", HEATING_CIRCUIT_SENSORS),
    )
    return [
        MyGekkoPropertySensor(coordinator, entity, prefix, description)
        for entities, prefix, descriptions in groups
        for entity in entities or []
        for description in descriptions
    ]
