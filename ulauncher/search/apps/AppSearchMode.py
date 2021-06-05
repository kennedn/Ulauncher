import json

import dbus

from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.search.BaseSearchMode import BaseSearchMode
from ulauncher.search.apps.AppDb import AppDb
from ulauncher.search.apps.AppIconCache import AppIconCache
from ulauncher.search.apps.AppResultItem import AppResultItem
from ulauncher.api.shared.action.BaseAction import BaseAction


class ActivateAppAction(BaseAction):

    def __init__(self, activate_cb):
        self.activate_cb = activate_cb

    def keep_app_open(self):
        return False

    def run(self):
        self.activate_cb()


class AppSearchMode(BaseSearchMode):
    """
    :type list search_modes: a list of other :class:`SearchMode` objects that provide additional result items
    """

    def __init__(self, search_modes):
        self.search_modes = search_modes
        self.app_db = AppDb.get_instance()

        self.app_icon_cache = AppIconCache.get_instance()

        self.bus = dbus.SessionBus()

        obj = self.bus.get_object(
            'org.gnome.Shell', '/org/gnome/Shell')
        eval_call = obj.get_dbus_method(
            'Eval', dbus_interface='org.gnome.Shell')

        self.get_active_windows = lambda: eval_call(r'''
            Main.Shell.AppSystem.get_default().get_running().map(
                app => {
                    return {
                        id: app.get_id(),
                    };
                }
            )
        ''')

        self.activate_window = lambda app_id: eval_call(f'''
            Main.activateWindow(
                Main.Shell.AppSystem.get_default().lookup_app(
                    {json.dumps(app_id)}
                ).get_windows()[0]
            )
        ''')

    def patch_on_enter(self, result_item):
        def new_on_enter(query, old_on_enter=result_item.on_enter):
            old_on_enter(query)
            activate = lambda: self.activate_window(
                result_item.record['desktop_file_short'])
            return ActivateAppAction(activate)
        return new_on_enter

    def is_enabled(self, query):
        """
        AppSearchMode is a default search mode and is always enabled
        """
        return True

    def handle_query(self, query):
        result_list = self.app_db.find(query)
        for mode in self.search_modes:
            result_list.extend(mode.get_searchable_items())

        if not result_list and query:
            # default search
            result_list = []
            for mode in self.search_modes:
                result_list.extend(mode.get_default_items())

        status, active_apps = self.get_active_windows()
        if status:
            active_apps = {app['id'] for app in json.loads(active_apps)}

            for r in result_list:
                if isinstance(r, AppResultItem):
                    if r.record['desktop_file_short'] in active_apps:
                        r.on_enter = self.patch_on_enter(r)

        return RenderResultListAction(result_list)
