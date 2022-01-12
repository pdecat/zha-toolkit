import importlib
import logging

import voluptuous as vol
import zigpy.types as t

import homeassistant.helpers.config_validation as cv

from . import utils as u

DEPENDENCIES = ["zha"]

DOMAIN = "zha_custom"

ATTR_COMMAND = "command"
ATTR_COMMAND_DATA = "command_data"
ATTR_IEEE = "ieee"
DATA_ZHAC = "zha_custom"

SERVICE_CUSTOM = "execute"

LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMAS = {
    SERVICE_CUSTOM: vol.Schema(
        {
            vol.Optional(ATTR_IEEE): cv.string,  # was: t.EUI64.convert, - keeping ieee for compatibility
            vol.Optional(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_COMMAND_DATA): cv.string,
        },
        extra=vol.ALLOW_EXTRA,
    )
}


async def async_setup(hass, config):
    """Set up ZHA from config."""

    if DOMAIN not in config:
        return True

    try:
        zha_gw = hass.data["zha"]["zha_gateway"]
    except KeyError:
        return True

    async def custom_service(service):
        """Run command from custom module."""
        LOGGER.info("Running custom service: %s", service)

        ieee_str = service.data.get(ATTR_IEEE)
        cmd = service.data.get(ATTR_COMMAND)
        cmd_data = service.data.get(ATTR_COMMAND_DATA)

        importlib.reload(u)

        app=zha_gw.application_controller

        ieee = await u.get_ieee(app, zha_gw, service.data.get(ATTR_IEEE))
        if ieee is not None: 
            LOGGER.debug("'ieee' parameter: '%s' -> IEEE Addr: '%s'", ieee_str, ieee)

        mod_path = "custom_components.{}".format(DOMAIN)
        try:
            module = importlib.import_module(mod_path)
        except ImportError as err:
            LOGGER.error("Couldn't load %s module: %s", DOMAIN, err)
            return
        importlib.reload(module)
        LOGGER.debug("module is %s", module)
        if cmd:
            handler = getattr(module, "command_handler_{}".format(cmd))
            await handler(
                zha_gw.application_controller, zha_gw, ieee, cmd, cmd_data, service
            )
        else:
            await module.default_command(
                zha_gw.application_controller, zha_gw, ieee, cmd, cmd_data, service
            )

    hass.services.async_register(
        DOMAIN, SERVICE_CUSTOM, custom_service, schema=SERVICE_SCHEMAS[SERVICE_CUSTOM]
    )
    return True


async def default_command(app, listener, ieee, cmd, data, service):
    LOGGER.debug("running default command: %s", service)


async def command_handler_handle_join(app, listener, ieee, cmd, data, service):
    """Rediscover a device.
    ieee -- ieee of the device
    data -- nwk of the device in decimal format
    """
    LOGGER.debug("running 'handle_join' command: %s", service)
    if ieee is None:
        LOGGER.debug("Provide 'ieee' parameter for %s", cmd)
        raise Exception("ieee parameter missing")
    if data is None:
        dev = None
        try:
            dev = app.get_device(ieee=ieee)
            data = dev.nwk
            if data is None:
                raise Exception("Missing NWK for device '{}'".format(ieee))
            LOGGER.debug("Using NWK '%s' for '%s'", data, ieee)
        except Exception as e:
            LOGGER.debug("Device '%s' not found in device table, provide NWK address", ieee)
            raise e

    app.handle_join(u.str2int(data), ieee, 0)


async def command_handler_scan_device(*args, **kwargs):
    """Scan a device for all supported attributes and commands.
    ieee -- ieee of the device to scan

    ToDo: use manufacturer_id to scan for manufacturer specific clusters/attrs.
    """

    from . import scan_device

    importlib.reload(scan_device)

    await scan_device.scan_device(*args, **kwargs)


async def command_handler_get_groups(*args, **kwargs):
    """Get all groups a device is member of.
    ieee -- ieee of the device to issue "get_groups" cluster command
    """

    from . import groups

    importlib.reload(groups)

    await groups.get_groups(*args, **kwargs)


async def command_handler_add_group(*args, **kwargs):
    """Add a group to the device.
    ieee -- device to issue "add_group" Groups cluster command
    data -- group_id of the group to add, in 0xXXXX format
    """
    from . import groups

    importlib.reload(groups)

    await groups.add_group(*args, **kwargs)


async def command_handler_remove_group(*args, **kwargs):
    """Remove a group from the device.
    ieee -- device to issue "remove_group" Groups cluster command
    data -- group_id of the group to remove in 0xXXXX format
    """
    from . import groups

    importlib.reload(groups)

    await groups.remove_group(*args, **kwargs)


async def command_handler_remove_all_groups(*args, **kwargs):
    """Remove all groups from a device.
    ieee -- device to issue "remove all" Groups cluster command
    """
    from . import groups

    importlib.reload(groups)

    await groups.remove_all_groups(*args, **kwargs)


async def command_handler_bind_group(*args, **kwargs):
    """Add group binding to a device.
    ieee -- ieee of the remote (device configured with a binding)
    data -- group_id
    """
    from . import binds

    importlib.reload(binds)

    await binds.bind_group(*args, **kwargs)


async def command_handler_unbind_group(*args, **kwargs):
    """Remove group binding from a device.
    ieee -- ieee of the remote (device configured with a binding)
    data -- group_id
    """
    from . import binds

    importlib.reload(binds)

    await binds.unbind_group(*args, **kwargs)


async def command_handler_bind_ieee(*args, **kwargs):
    """IEEE bind device.
    ieee -- ieee of the remote (device configured with a binding)
    data -- ieee of the target device (device remote sends commands to)
    """
    from . import binds

    importlib.reload(binds)

    await binds.bind_ieee(*args, **kwargs)


async def command_handler_unbind_coordinator(*args, **kwargs):
    """IEEE bind device.
    ieee -- ieee of the device to unbind from coordinator
    data -- cluster ID to unbind
    """
    from . import binds

    importlib.reload(binds)

    await binds.unbind_coordinator(*args, **kwargs)


async def command_handler_rejoin(app, listener, ieee, cmd, data, service):
    """Leave and rejoin command.
    data -- device ieee to allow joining through
    ieee -- ieee of the device to leave and rejoin
    """
    if ieee is None:
        LOGGER.error("missing ieee")
        return
    LOGGER.debug("running 'rejoin' command: %s", service)
    src = app.get_device(ieee=ieee)

    if data is None:
        await app.permit()
    else:
        await app.permit(node=convert_ieee(data))
    res = await src.zdo.request(0x0034, src.ieee, 0x01)
    LOGGER("%s: leave and rejoin result: %s", src, ieee, res)


def command_handler_get_zll_groups(*args, **kwargs):
    from . import groups

    importlib.reload(groups)

    return groups.get_zll_groups(*args, **kwargs)


def command_handler_add_to_group(*args, **kwargs):
    """Add device to a group."""
    from . import groups

    importlib.reload(groups)

    return groups.add_to_group(*args, **kwargs)


def command_handler_remove_from_group(*args, **kwargs):
    """Remove device from a group."""
    from . import groups

    importlib.reload(groups)

    return groups.remove_from_group(*args, **kwargs)


def command_handler_sinope(*args, **kwargs):
    from . import sinope

    importlib.reload(sinope)

    return sinope.sinope_write_test(*args, **kwargs)


def command_handler_attr_read(*args, **kwargs):
    from . import zcl_attr

    importlib.reload(zcl_attr)

    return zcl_attr.attr_read(*args, **kwargs)


def command_handler_attr_write(*args, **kwargs):
    from . import zcl_attr

    importlib.reload(zcl_attr)

    return zcl_attr.attr_write(*args, **kwargs)


def command_handler_conf_report(*args, **kwargs):
    from . import zcl_attr

    importlib.reload(zcl_attr)

    return zcl_attr.conf_report(*args, **kwargs)


def command_handler_get_routes_and_neighbours(*args, **kwargs):
    """Scan a device for neighbours and routes.
    ieee -- ieee of the device to scan
    """
    from . import neighbours

    importlib.reload(neighbours)

    return neighbours.routes_and_neighbours(*args, **kwargs)


def command_handler_all_routes_and_neighbours(*args, **kwargs):
    """Scan all devices for neighbours and routes. """
    from . import neighbours

    importlib.reload(neighbours)

    return neighbours.all_routes_and_neighbours(*args, **kwargs)


def command_handler_leave(*args, **kwargs):
    from . import zdo

    importlib.reload(zdo)

    return zdo.leave(*args, **kwargs)


def command_handler_ieee_ping(*args, **kwargs):
    from . import zdo

    importlib.reload(zdo)

    return zdo.ieee_ping(*args, **kwargs)


def command_handler_zigpy_deconz(*args, **kwargs):
    """Zigpy deconz test. """
    from . import zigpy_deconz

    importlib.reload(zigpy_deconz)

    return zigpy_deconz.zigpy_deconz(*args, **kwargs)


def command_handler_ezsp_set_channel(*args, **kwargs):
    """Set EZSP radio channel. """
    from . import ezsp

    importlib.reload(ezsp)

    return ezsp.set_channel(*args, **kwargs)


def command_handler_ezsp_get_token(*args, **kwargs):
    """Set EZSP radio channel. """
    from . import ezsp

    importlib.reload(ezsp)

    return ezsp.get_token(*args, **kwargs)


def command_handler_ezsp_start_mfg(*args, **kwargs):
    """Set EZSP radio channel. """
    from . import ezsp

    importlib.reload(ezsp)

    return ezsp.start_mfg(*args, **kwargs)


def command_handler_ezsp_get_keys(*args, **kwargs):
    """Get EZSP keys. """
    from . import ezsp

    importlib.reload(ezsp)

    return ezsp.get_keys(*args, **kwargs)


def command_handler_ezsp_add_key(*args, **kwargs):
    """Add transient link key. """
    from . import ezsp

    importlib.reload(ezsp)
    return ezsp.add_transient_key(*args, **kwargs)


def command_handler_ezsp_get_ieee_by_nwk(*args, **kwargs):
    """Get EZSP keys. """
    from . import ezsp

    importlib.reload(ezsp)
    return ezsp.get_ieee_by_nwk(*args, **kwargs)


def command_handler_ezsp_get_policy(*args, **kwargs):
    """Get EZSP keys. """
    from . import ezsp

    importlib.reload(ezsp)
    return ezsp.get_policy(*args, **kwargs)


def command_handler_ezsp_clear_keys(*args, **kwargs):
    """Clear key table."""
    from . import ezsp

    importlib.reload(ezsp)

    return ezsp.clear_keys(*args, **kwargs)


def command_handler_ezsp_get_config_value(*args, **kwargs):
    """Get EZSP config value."""
    from . import ezsp

    importlib.reload(ezsp)

    return ezsp.get_config_value(*args, **kwargs)


def command_handler_ezsp_get_value(*args, **kwargs):
    """Get EZSP value."""
    from . import ezsp

    importlib.reload(ezsp)

    return ezsp.get_value(*args, **kwargs)


def command_handler_ota_notify(*args, **kwargs):
    """Set EZSP radio channel. """
    from . import ota

    importlib.reload(ota)

    return ota.notify(*args, **kwargs)


def command_handler_zdo_join_with_code(*args, **kwargs):
    from . import zdo

    importlib.reload(zdo)

    return zdo.join_with_code(*args, **kwargs)


def command_handler_zdo_update_nwk_id(*args, **kwargs):
    from . import zdo

    importlib.reload(zdo)

    return zdo.update_nwk_id(*args, **kwargs)


def command_handler_zdo_scan_now(*args, **kwargs):
    from . import zdo

    importlib.reload(zdo)

    return zdo.topo_scan_now(*args, **kwargs)


def command_handler_zdo_flood_parent_annce(*args, **kwargs):
    from . import zdo

    importlib.reload(zdo)

    return zdo.flood_parent_annce(*args, **kwargs)


def command_handler_znp_backup(*args, **kwargs):
    """ Backup ZNP network information. """
    from . import znp

    importlib.reload(znp)

    return znp.znp_backup(*args, **kwargs)


def command_handler_znp_restore(*args, **kwargs):
    """ Restore ZNP network information. """
    from . import znp

    importlib.reload(znp)

    return znp.znp_restore(*args, **kwargs)


def command_handler_zcl_cmd(*args, **kwargs):
    """ Perform scene command. """
    from . import zcl_cmd

    importlib.reload(zcl_cmd)

    return zcl_cmd.zcl_cmd(*args, **kwargs)


def command_handler_znp_nvram_backup(*args, **kwargs):
    """ Backup ZNP network information. """
    from . import znp

    importlib.reload(znp)

    return znp.znp_nvram_backup(*args, **kwargs)


def command_handler_znp_nvram_restore(*args, **kwargs):
    """ Restore ZNP network information. """
    from . import znp

    importlib.reload(znp)

    return znp.znp_nvram_restore(*args, **kwargs)


def command_handler_znp_nvram_reset(*args, **kwargs):
    """ Restore ZNP network information. """
    from . import znp

    importlib.reload(znp)

    return znp.znp_nvram_reset(*args, **kwargs)
