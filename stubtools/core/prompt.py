# --------------------------------------------
# Copyright 2018 Grant Viklund
# @Author: Grant Viklund
# @Date:   2018-10-31 14:00:21
# @Last modified by:   Grant Viklund
# @Last Modified time: 2018-11-01 17:41:52
# --------------------------------------------

def selection_list(sel_list, prompt="Make a section", title="Selection", terminal_width=80, exitable=True, as_string=False):

    word_width = 1
    margin = 6
    # count = len(sel_list)     # Can be used later for validation (i.e. selection out of range)

    for sel in sel_list:
        ln = len(sel)
        if ln > word_width:
            word_width = ln

    columns = int(terminal_width / (word_width + margin))

    if columns < 1:
        columns = 1

    old_row = 0
    output = ""

    print( "\n#%s" % ("-" * (terminal_width - 1)))
    print( "# %s\n" % title)

    for c, sel in enumerate(sel_list):
        row = int(c / columns)
        col = c % columns

        if row != old_row:
            print(output)
            output = ""

        output += "%2d) %s%s  " % ( (c + 1), sel, (" " * (word_width - len(sel)) ) )
        old_row = row

    if exitable:
        print( "\n 0) Exit\n")

    # Make the selection
    selection = int( input(prompt + " > ") )

    if selection == 0:
        return None

    sel_index = selection - 1

    if as_string:
        return sel_list[ sel_index ]

    return sel_index


def multi_selection_list(sel_list, prompt="Make a section", title="Selection", terminal_width=80, exitable=True, as_string=False, selected=[]):

    word_width = 1
    margin = 10
    # count = len(sel_list)     # Can be used later for validation (i.e. selection out of range)

    for sel in sel_list:
        ln = len(sel)
        if ln > word_width:
            word_width = ln

    columns = int(terminal_width / (word_width + margin))

    if columns < 1:
        columns = 1

    old_row = 0
    output = ""

    print( "\n#%s" % ("-" * (terminal_width - 1)))
    print( "# %s\n" % title)

    for c, sel in enumerate(sel_list):
        row = int(c / columns)
        col = c % columns

        if row != old_row:
            print(output)
            output = ""

        if sel in selected:
            sel_value = "*"
        else:
            sel_value = " "

        output += "(%s) %2d) %s%s  " % ( sel_value, (c + 1), sel, (" " * (word_width - len(sel)) ) )
        old_row = row

    if exitable:
        print( "\n d) Done\n")
        # print( "\n00) Cancel\n")

    # Make the selection
    new_selected = input(prompt + " > ").split()

    # Toggle selection based on new_selected results

    if new_selected[0] == "d":
        selected.sort()
        return selected
    else:
        for i in new_selected:
            selected.append(sel_list[int(i) - 1])

        return multi_selection_list(sel_list, prompt=prompt, title=title, terminal_width=terminal_width, exitable=exitable, as_string=as_string, selected=selected)


"""
from stubtools.core.prompt import selection_list, multi_selection_list
from django.views.generic.base import View
from stubtools.core import get_all_subclasses
view_classes = get_all_subclasses(View, ignore_modules=["django.views.i18n", "django.contrib.admin.views"])
VIEW_CLASS_SETTINGS = {'TemplateView':{'import':""}, 'ListView':{}, 'DetailView':{}, 'RedirectView':{}}

for cl in view_classes:  
    
    class_name = cl.__name__  
    if class_name not in VIEW_CLASS_SETTINGS:
        VIEW_CLASS_SETTINGS[class_name] = {}
    
    VIEW_CLASS_SETTINGS[class_name]['import'] = cl

classes = list(VIEW_CLASS_SETTINGS.keys())

multi_selection_list(classes)
"""