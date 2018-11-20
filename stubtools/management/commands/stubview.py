#--------------------------------------------
# Copyright 2013-2018, Grant Viklund
# @Author: Grant Viklund
# @Date:   2017-02-20 13:50:51
# @Last Modified by:   Grant Viklund
# @Last Modified time: 2018-11-19 16:09:28
#--------------------------------------------

import re, os.path
import django
import pprint

from django.core.management.base import CommandError
from django.views.generic.base import View
from django.template.loader import get_template

# from jinja2 import Environment, PackageLoader, select_autoescape

from stubtools.core import FileAppCommand, class_name, version_check, get_all_subclasses, split_camel_case, underscore_camel_case, parse_app_input, get_file_lines
from stubtools.core.prompt import ask_question, ask_yes_no_question, selection_list, horizontal_rule
from stubtools.core.parse import IMPORT_REGEX, get_classes_and_functions_start, get_pattern_line, get_all_pattern_lines, get_classes_and_functions, get_import_range
from stubtools.core.view_classes import VIEW_CLASS_DEFAULT_SETTINGS, VIEW_CLASS_SETTINGS, STUBTOOLS_IGNORE_MODULES
from stubtools.core.file import write_file


class Command(FileAppCommand):
    args = '<app.view.view_class>'
    help = 'creates a template and matching view for the given view name'
    terminal_width = 80
    debug = False

    def handle(self, *args, **kwargs):
        if len(args) < 1:
            raise CommandError('Need to pass App.View names')

        # batch process app views
        try:
            for app_view in args:
                # SPLIT THE APP, VIEW AND VIEW_CLASS
                app, view, view_class = parse_app_input(app_view)
                self.process(app, view, view_class)
        except KeyboardInterrupt:
            print("\nExiting...")
            return


    def get_context(self, app, view, view_setting_key, **kwargs):

        view_class_settings = self.get_class_settings(View, ignore_modules=STUBTOOLS_IGNORE_MODULES, settings=VIEW_CLASS_SETTINGS)      # todo: move this over to a settings option
        view_class_shortname_map = dict([(v['class_name'], k) for k, v in view_class_settings.items()])

        # PICK THE VIEW CLASS TO USE BASED ON A LIST OF AVAILABLE CLASSES IF NOT SET IN THE COMMAND LINE
        if not view_setting_key:
            view_short_key = selection_list(list( view_class_shortname_map.keys() ), as_string=True)
            view_setting_key = view_class_shortname_map[view_short_key]

        if view_setting_key:
            print("\nUsing Module Setting for '%s'" % view_setting_key)

        view_class = view_class_settings[view_setting_key]['class_name']

        print("View Class: %s" % view_class)

        if not view:
            default = "My%s" % view_class
            view = input("What is the name of the view? [%s] > " % default) or default

        # MAKE SURE AT LEAST THE FIRST LETTER OF THE VIEW NAME IS CAPITALIZED
        view = view[0].upper() + view[1:]

        view_name = "_".join(split_camel_case(view)).lower()

        render_ctx = {'app':app, 'view':view, 'view_name':view_name, 'views':[],
                        'view_class':view_class, 'attributes':{}, 
                        'view_class_module': view_class_settings[view_setting_key]['module'] }

        render_ctx.update(kwargs)  # Update with any context info passed in.

        attr_ctx = {'app_label': app, 'view_name':view_name}

        key_remove_attr_list = []   # This is so defaults are available while the questioning is going on so defaults can be applied to other attrs.

        if not 'template_in_app' in kwargs:
            render_ctx['template_in_app'] = ask_yes_no_question("Place templates at the app level?", default=True, required=True)

        render_ctx['constructor_template'] = view_class_settings[view_setting_key].get("template", VIEW_CLASS_DEFAULT_SETTINGS['template'])

        ################
        # QUERIES:
        # Query the user to build the attribute values

        # print(view_setting_key)

        queries = []
        queries.extend(view_class_settings[view_setting_key].get("queries", []))

        default_queries = []
        default_queries.extend(VIEW_CLASS_DEFAULT_SETTINGS['queries'])

        default_values = view_class_settings[view_setting_key].get("default_values", {})

        for item in default_queries:
            if item['key'] in default_values:
                item['default'] = default_values[item['key']]

        queries.extend(default_queries)

        if 'model' in kwargs:       # If a model is explicitly passed in to the method, use that value.  It will be skipped in the queries.
            attr_ctx['model'] = kwargs['model']
            render_ctx['model'] = kwargs['model']
            print("** Working with Model -> %s" % kwargs['model'])

        for query in queries:
            key = query['key']

            # print("KEY: %s" % key)

            if key in kwargs:   # Don't ask the question if an answer is already provided (usually from chaining).
                continue

            default = query.get("default", None)
            ignore_default = query.get("ignore_default", False)

            # Update the attribute context with the results of render_ctx['attributes'] before creating the default value
            attr_ctx.update(render_ctx['attributes'])

            if 'model' in attr_ctx:
                attr_ctx['model_name'] = "_".join(split_camel_case(attr_ctx['model'])).lower()

            # Create the default value so it can be used in the query prompt
            if default:
                default = default % attr_ctx    # Update the default value with the attr_ctx

            answer = ask_question(query["question"], default=default, required=query.get("required", False) )

            # If the result is seto to 'ignore_default' it will be poped out of the context when queries are done.
            # In other words, the value will be kept only if it's not the default after the queries are over.
            if ignore_default and answer == default:
                key_remove_attr_list.append(key)

            value_type = query.get('attr_type', None)

            if value_type == "str":
                answer = '\"%s\"' % answer

            # This way if an attribute value is updated, it's reapplied to the question context
            if query.get('as_atttr', True):
                render_ctx['attributes'][key] = answer
            else:
                render_ctx[key] = answer

        for key in key_remove_attr_list:
            del render_ctx['attributes'][key]

        view_suffix = view_class_settings[view_setting_key].get("view_suffix", "View")     # Given the view type, there is a common convention for appending to the name of the "page's" View's Class

        render_ctx['description'] = ask_question("Did you want to add a quick description?")

        # POP VIEW OFF THE NAME PARTS IF IT IS THERE
        if view.endswith(view_suffix):
            render_ctx['page_class'] = view
        else:
            render_ctx['page_class'] = view + view_suffix

        # Break the Name up into parts
        name_parts = split_camel_case(view[:(-1 * len(view_suffix))])

        render_ctx['page'] = "_".join(name_parts).lower()   # Name used in the URL and template
        render_ctx['page_name'] = ' '.join(name_parts)      # Title Friendly Format

        if version_check("gte", "2.0.0"):
            render_ctx['resource_method'] = "path"
        else:
            render_ctx['resource_method'] = "url"

        render_ctx['class_based_view'] = True

        return render_ctx

    def process(self, app, view, view_class, **kwargs):

        render_ctx = self.get_context(app, view, view_class, **kwargs)

        view_file = os.path.join(app, "views.py")
        url_file = os.path.join(app, "urls.py")

        if render_ctx['template_in_app']:
            template_file = os.path.join(app, "templates", *render_ctx['attributes']['template_name'][1:-1].split("/"))
        else:
            template_file = os.path.join("templates", *render_ctx['attributes']['template_name'][1:-1].split("/"))     # todo: get the template folder name from the settings

        #######################
        # PARSE view.py
        #######################

        # Slice and Dice!
        data_lines = get_file_lines(view_file)
        line_count = len(data_lines)

        # Establish the Segments
        import_start_index = 0
        import_end_index = 0
        class_func_start = get_classes_and_functions_start(data_lines)
        class_func_end = line_count

        # Segment Values
        pre_import = None
        pre_view = None
        post_view = None

        import_start_index, import_end_index = get_import_range("^from %(view_class_module)s import (.+)" % render_ctx, data_lines[:class_func_start])
        
        if import_start_index > import_end_index:
            render_ctx['view_import_statement'] = create_import_line(data_lines[import_start_index], render_ctx['view_class_module'], render_ctx['view_class'])
        else:
            render_ctx['view_import_statement'] = "from %(view_class_module)s import %(view_class)s" % render_ctx

        # 3) Find where the post_view starts

        # Search backwards until there is line that is not blank or a starting with a '#'.
        # This is here to provide recognition for footers on files that may be there
        # todo: Add support for """/''' blocks?

        for c, line in reversed(list(enumerate(data_lines))):
            cleaned_line = line.strip()

            if cleaned_line:
                if not cleaned_line.startswith("#"):
                    class_func_end = c + 1
                    break

        # 4) Build the sections

        render_ctx['view_header'] = "".join(data_lines[:import_start_index])
        render_ctx['view_pre_view'] = "".join(data_lines[import_end_index:class_func_end])
        render_ctx['view_footer'] = "".join(data_lines[class_func_end:])

        pp = pprint.PrettyPrinter(indent=4)


        #######################
        # PARSE urls.py
        #######################

        # In Django 2.x, the resource pattern changed from 'url' to 'path'

        # from django.conf.urls import url          # < 2.0
        # from django.urls import path, re_path     # 2.0+

        # from . import views

        # urlpatterns = [
        #     url(r'^profile/$', views.ProfileView.as_view(), name='poop-profile'),
        # ]

        # Slice and Dice!
        data_lines = get_file_lines(url_file)
        line_count = len(data_lines)

        resource_pattern_start = get_pattern_line("(urlpatterns =)", data_lines, default=line_count)
        resource_pattern_end = get_pattern_line("]", data_lines[resource_pattern_start:], default=0) + resource_pattern_start    # Look for the ']' after the urlpatterns
        render_ctx['existing_patterns'] = [ p.strip() for p in get_all_pattern_lines(r"(url\(|path\(|re_path\()", data_lines) ]

        import_block = data_lines[:resource_pattern_start]

        if version_check("gte", "2.0.0"):
            url_import_line = get_pattern_line("from django.urls import", import_block)

            if url_import_line == None:
                # If there is no up-to-date import line, see if this is importing an old module, if so, see about updating the old resources
                url_import_line = get_pattern_line("from django.conf.urls import url", import_block)

                if url_import_line == None:
                    url_import_line = len(import_block)

                    for c, line in enumerate(import_block):
                        line.strip()
                        print(c)
                        print(line)                        
                        if not line.startswith("#"):    # Skip passed any header comments at the start of a file
                            url_import_line = c
                            break
            
            render_ctx['url_import_statement'] = "from django.urls import path, re_path"    # todo: this could be better and more flexible.  Need to check to see ALL modules that are loaded

            # Update the Exisitng Patterns here
            render_ctx['existing_patterns'] = [re.sub(r'url\(', r're_path(', item) for item in render_ctx['existing_patterns']]
        else:
            url_import_line = get_pattern_line("^from django.conf.urls import (.+)", import_block, default=0)
            render_ctx['url_import_statement'] = "from django.conf.urls import url"

        # If the view import line is missing, make sure it's there
        if get_pattern_line("^from \. import(.+)", import_block) == None:
            render_ctx['url_import_statement'] = render_ctx['url_import_statement'] + "\nfrom . import views"

        if url_import_line > 0:
            render_ctx['pre_import'] = "".join(data_lines[:url_import_line])
        else:
            render_ctx['pre_import'] = ""

        pre_url_lines = data_lines[url_import_line:resource_pattern_start]

        # Check for old import line module import
        if version_check("gte", "2.0.0"):
            old_url_line = get_pattern_line("from django.conf.urls", pre_url_lines)
            if old_url_line != None:
                pre_url_lines.pop(old_url_line)

        render_ctx['pre_urls'] = "".join(pre_url_lines)
        render_ctx['post_urls'] = "".join(data_lines[resource_pattern_end + 1:])

        # Get the import lines

        # 5) Assemble the file

        #######################
        # RENDER THE TEMPLATES
        #######################

        if self.debug:
            print( horizontal_rule() )
            print("RENDER CONTEXT:")
            pp.pprint(render_ctx)
            print( horizontal_rule() )

        #######################
        # Render Templates

        # load templates using Django's settings so users can create customized override templates.
        view_template = get_template('stubtools/stubview/view.py.j2', using='jinja2')
        url_template = get_template('stubtools/stubview/urls.py.j2', using='jinja2')
        constructor_template = get_template('stubtools/stubview/' + render_ctx['constructor_template'], using='jinja2')

        view_result = view_template.render(context=render_ctx)
        urls_result = url_template.render(context=render_ctx)
        template_results = constructor_template.render(context=render_ctx)

        #######################
        # Writing Output

        if self.debug:
            print("views.py RESULT:")
            print(view_result)

            print( horizontal_rule() )
            print("urls.py RESULT:")
            print( horizontal_rule() )
            print(urls_result)

            print( horizontal_rule() )
            print("%s RESULT:" % template_file)
            print( horizontal_rule() )
            print(template_results)

            print( horizontal_rule() )
            print("FILES:")
            print("    VIEW FILE: %s" % view_file)
            print("    URL FILE: %s" % url_file)
            print("    TEMPLATE FILE: %s" % template_file)

        if not self.debug:
            self.write_file(view_file, view_result)
            self.write_file(url_file, urls_result)

            # Only write if it does not exist:
            if not os.path.exists(template_file):
                self.write_file(template_file, template_results)

        self.render_ctx = render_ctx    # Appended to the end so it can be queried after.


