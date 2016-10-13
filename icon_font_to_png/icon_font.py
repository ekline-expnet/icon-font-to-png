from __future__ import unicode_literals
from six import unichr

import os
import re
import tinycss
from collections import OrderedDict

from PIL import Image, ImageFont, ImageDraw


class IconFont(object):
    """Base class that represents web icon font"""
    def __init__(self, css_file, ttf_file, keep_prefix=False):
        """
        :param css_file: path to icon font CSS file
        :param ttf_file: path to icon font TTF file
        :param keep_prefix: whether to keep common icon prefix
        """
        self.css_file = css_file
        self.ttf_file = ttf_file
        self.keep_prefix = keep_prefix

        self.css_icons, self.common_prefix = self.load_css()

    def load_css(self):
        """
        Creates a dict of all icons available in CSS file, and finds out
        what's their common prefix.

        :returns sorted icons dict, common icon prefix
        """
        icons = dict()
        common_prefix = None
        parser = tinycss.make_parser('page3')
        stylesheet = parser.parse_stylesheet_file(self.css_file)

        is_icon = re.compile("\.(.*):before,?")

        for rule in stylesheet.rules:
            selector = rule.selector.as_css()

            # Skip CSS classes that are not icons
            if not is_icon.match(selector):
                continue

            # Find out what the common prefix is
            if common_prefix is None:
                common_prefix = selector[1:]
            else:
                common_prefix = os.path.commonprefix((common_prefix,
                                                      selector[1:]))

            for match in is_icon.finditer(selector):
                name = match.groups()[0]
                for declaration in rule.declarations:
                    if declaration.name == "content":
                        val = declaration.value.as_css()
                        # Strip quotation marks
                        if re.match("^['\"].*['\"]$", val):
                            val = val[1:-1]
                        icons[name] = unichr(int(val[1:], 16))

        common_prefix = common_prefix or ''

        # Remove common prefix
        if not self.keep_prefix and len(common_prefix) > 0:
            non_prefixed_icons = {}
            for name in icons.keys():
                non_prefixed_icons[name[len(common_prefix):]] = icons[name]
            icons = non_prefixed_icons

        sorted_icons = OrderedDict(sorted(icons.items(), key=lambda t: t[0]))

        return sorted_icons, common_prefix

    def scale_font(self, ttf, icon, size, scale):
        """
        Scales a font to make sure the font fits inside boudary

        :param ttf: file path to the ttf file
        :param icon: valid icon name for graphic to scale
        :param size: icon size in pixels
        :param scale: scaling factor between 0 and 1,
                      or 'auto' for automatic scaling

        :returns the scaled font, width, height, bbox of image

        # If auto-scaling is enabled, we need to make sure the resulting
        # graphic fits inside the boundary. The values are rounded and may be
        # off by a pixel or two, so we may need to do a few iterations.
        # The use of a decrementing multiplication factor protects us from
        # getting into an infinite loop.
        """
        Helper function to scale a font
        if scale == 'auto':
            scale_factor = 1
        else:
            scale_factor = float(scale)

        image = Image.new("RGBA", (size, size), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        font = ImageFont.truetype(ttf, int(size * scale_factor))
        width, height = draw.textsize(self.css_icons[icon], font=font)

        if scale == 'auto':
            iteration = 0
            factor = 1

            while True:
                width, height = draw.textsize(self.css_icons[icon], font=font)

                # Check if the image fits
                dim = max(width, height)
                if dim > size:
                    font = ImageFont.truetype(self.ttf_file,
                                              int(size * size/dim * factor))
                else:
                    break

                # Adjust the factor every two iterations
                iteration += 1
                if iteration % 2 == 0:
                    factor *= 0.99
        # Get bounding box
        bbox = image.getbbox()
        return font, width, height, bbox

    def export_icon(self, icon, size, color='black', scale='auto',
                    filename=None, export_dir='exported', wrapper_icon=''):
        """
        Exports given icon with provided parameters.

        If the desired icon size is less than 150x150 pixels, we will first
        create a 150x150 pixels image and then scale it down, so that
        it's much less likely that the edges of the icon end up cropped.

        :param icon: valid icon name
        :param filename: name of the output file
        :param size: icon size in pixels
        :param color: color name or hex value
        :param scale: scaling factor between 0 and 1,
                      or 'auto' for automatic scaling
        :param export_dir: path to export directory
        :param wrapper_icon: valid icon name to use as an outer wrapper
        """
        if wrapper_icon == '':
            self.export_icon_with_wrapper(icon=icon, size=size,
                color=color, scale=scale, filename=filename,
                export_dir=export_dir)
        else:
            self.export_icon_with_wrapper(icon=icon, size=size,
                color=color, scale=scale, filename=filename,
                export_dir=export_dir, wrapper_icon=wrapper_icon)

    def export_icon_no_wrapper(self, icon, size, color='black', scale='auto',
                    filename=None, export_dir='exported'):
        """
        Exports given icon with provided parameters.

        If the desired icon size is less than 150x150 pixels, we will first
        create a 150x150 pixels image and then scale it down, so that
        it's much less likely that the edges of the icon end up cropped.

        :param icon: valid icon name
        :param filename: name of the output file
        :param size: icon size in pixels
        :param color: color name or hex value
        :param scale: scaling factor between 0 and 1,
                      or 'auto' for automatic scaling
        :param export_dir: path to export directory
        """
        org_size = size
        size = max(150, size)

        font, width, height, bbox = self.scale_font(ttf=ttf, icon=icon,
            size=size, scale=scale)

        # Create an alpha mask
        image_mask = Image.new("L", (size, size), 0)
        draw_mask = ImageDraw.Draw(image_mask)

        # Draw the icon on the mask
        draw_mask.text((float(size - width) / 2, float(size - height) / 2),
                       self.css_icons[icon], font=font, fill=255)

        # Create a solid color image and apply the mask
        icon_image = Image.new("RGBA", (size, size), color)
        icon_image.putalpha(image_mask)

        if bbox:
            icon_image = icon_image.crop(bbox)

        border_w = int((size - (bbox[2] - bbox[0])) / 2)
        border_h = int((size - (bbox[3] - bbox[1])) / 2)

        # Create output image
        out_image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out_image.paste(icon_image, (border_w, border_h))

        # If necessary, scale the image to the target size
        if org_size != size:
            out_image = out_image.resize((org_size, org_size), Image.ANTIALIAS)

        # Make sure export directory exists
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # Default filename
        if not filename:
            filename = icon + '.png'

        # Save file
        out_image.save(os.path.join(export_dir, filename))

    def export_icon_with_wrapper(self, icon, size, wrapper_icon,
        color='black', scale='auto', filename=None, export_dir='exported'):
        """
        Exports given icon with provided parameters.

        If the desired icon size is less than 150x150 pixels, we will first
        create a 150x150 pixels image and then scale it down, so that
        it's much less likely that the edges of the icon end up cropped.

        :param icon: valid icon name
        :param filename: name of the output file
        :param size: icon size in pixels
        :param color: color name or hex value
        :param scale: scaling factor between 0 and 1,
                      or 'auto' for automatic scaling
        :param export_dir: path to export directory
        :param wrapper_icon: valid icon name to use as an outer wrapper
        """
        if scale == 'auto':
            scale_factor = 1.0
        else:
            scale_factor = float(scale)

        full_scale = scale_factor
        scale_factor = float(scale_factor / 2.0)

        font, width, height, bbox = self.scale_font(ttf=self.ttf_file,
            icon=icon, size=size, scale=scale_factor)
        font2, width2, height2, bbox2 = self.scale_font(ttf=self.ttf_file,
            icon=wrapper_icon, size=size, scale=full_scale)

        # Create an alpha mask
        image_mask = Image.new("L", (size, size), 0)
        draw_mask = ImageDraw.Draw(image_mask)

        # Draw the icons on the mask
        draw_mask.text((float(size - width2) / 2, float(size - height2) / 2),
                       self.css_icons[wrapper_icon], font=font2, fill=255)
        draw_mask.text((float(size - width) / 2, float(size - height) / 2),
                       self.css_icons[icon], font=font, fill=255)

        # Create a solid color image and apply the mask
        icon_image = Image.new("RGBA", (size, size), color)
        icon_image.putalpha(image_mask)

        if bbox2:
            icon_image = icon_image.crop(bbox2)

        border_w = int((size - (bbox[2] - bbox[0])) / 2)
        border_h = int((size - (bbox[3] - bbox[1])) / 2)

        # Create output image
        out_image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out_image.paste(icon_image, (border_w, border_h))

        # If necessary, scale the image to the target size
        if org_size != size:
            out_image = out_image.resize((org_size, org_size), Image.ANTIALIAS)

        # Make sure export directory exists
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # Default filename
        if not filename:
            filename = icon + '.png'

        # Save file
        out_image.save(os.path.join(export_dir, filename))
