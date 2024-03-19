import pyblish.api

from openpype.hosts.photoshop import api as photoshop
from openpype.pipeline import OptionalPyblishPluginMixin
from openpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError  
)

from .common import ColorMatches


class ValidateLayersOrganizationRepair(pyblish.api.Action):
    """Just select the layers that are with errors"""

    label = "Select Layers"
    icon = "briefcase"
    on = "failed"

    def process(self, context, plugin):
        stub = photoshop.stub()
        stub.select_layers(layer['PSItem'] for layer in context.data['transientData'][ValidateLayersOrganization.__name__])
    
        return True


def _is_group(layer):
    return layer.group


def _check_color_error(color):
    return False if color in [data.value for data in ColorMatches] else True


def _generate_layer_with_error(layer, group_error, color_error):
    return {
        'PSItem': layer,
        'group_error': group_error,
        'color_error': color_error
    }


def _check_layer_is_clean(layer, layers_errors):
    have_parents = bool(layer.parents)
    have_bad_color = _check_color_error(layer.color_code)

    # return if layer is group, have no parent, and color is correct
    if not have_parents and not have_bad_color and _is_group(layer):
        return
    
    # return if layer have parent, and color is correct
    if have_parents and not have_bad_color and not _is_group(layer):
        return
    
    layers_errors.append(_generate_layer_with_error(
            layer=layer,
            # reverse the parent value to reflect the layer type(layer must have a parent, groups don't)
            group_error=have_parents if _is_group(layer) else not have_parents,
            color_error=have_bad_color
        )
        )


class ValidateLayersOrganization(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Validate the layer organization.

    Makes sure that no layers are out of groups, and that no groups are in another group.
    Also check if layers have color set on them
    """

    label = "Validate Layers Organization"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    optional = True
    actions = [ValidateLayersOrganizationRepair]
    active = False

    def process(self, context):

        if not self.is_active(context.data):
            return

        stub = photoshop.stub()
        layers = stub.get_layers()

        layers_errors = list()

        for layer in layers:
            _check_layer_is_clean(layer, layers_errors)

        if layers_errors:
            msg = (
                f"This layers need to be reorganized :\n-" +
                '\n-'.join([layer["PSItem"].name for layer in layers_errors if layer["group_error"]])
            )

            msg = msg + "\n" +(
                f"This layers have color issues :\n-" +
                '\n-'.join([layer["PSItem"].name for layer in layers_errors if layer["color_error"]])
            )

            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = layers_errors

            raise PublishXmlValidationError(self, msg)
