import os, fnmatch, re, threading, sublime, sublime_plugin, sys, codecs, subprocess

class _passManagerUtils:
    def __init__(self):
        self.window = sublime.active_window()

    def is_browser_view(self, view):
        if(view.is_scratch() == True and (view.name() == 'PassManager')):
              return True
        return False

    def find_browser_view(self):
        for view in self.window.views():
            if(self.is_browser_view(view)):
                return view
        return None

    def is_updating_view(self, view):
        if(view.is_scratch() == True and view.name() == 'Please wait.'):
            return True
        return False

    def find_updating_views(self):
        views = []
        for view in self.window.views():
            if(self.is_updating_view(view)):
                views.append(view)
        return views

    def close_all_updating(self):
        updatingviews = self.find_updating_views()
        for updatingview in updatingviews:
            self.window.focus_view(updatingview)
            self.window.run_command('close')

    def get_pass_executable(self):
        settings = sublime.load_settings('PassManager.sublime-settings')
        return settings.get('pass_executable') or 'pass'

    def get_password(self, password_path):
        try:            
            pass_executable = self.get_pass_executable()
            pipe = None
            cfp = subprocess.PIPE
            exec = [pass_executable,"show",password_path]
            if(sublime.platform() == 'windows'):
              CREATE_NO_WINDOW = 0x08000000
              pipe = subprocess.Popen(exec, stdout=cfp, stderr=cfp, shell=False, creationflags=CREATE_NO_WINDOW)
            else:
              pipe = subprocess.Popen(exec, stdout=cfp, stderr=cfp)
            out, err = pipe.communicate()
            return ""+str(out.decode("utf-8").strip())
        except:
            exc = sys.exc_info()[1]
            sublime.status_message(str(exc))
            pass

    def get_pass_storage(self):
        settings = sublime.load_settings('PassManager.sublime-settings')
        return settings.get('pass_directory') or False

    def _scandir(self, path):
      out = {'dirs':{}, 'files':[]}
      if( path.endswith(os.path.sep) == False ):
        path += os.path.sep
      for dirent in os.listdir(path):
        if( dirent.startswith('.') == False ):
          if( os.path.isdir(path+dirent) ):
            out['dirs'][dirent] = self._scandir(path+dirent)
          else:
            if( os.path.isfile(path+dirent)):
              out['files'].append(dirent)
      return out

    def add_semaphore(self, semaphore_name):
        self.window.settings().set(semaphore_name, True)

    def del_semaphore(self, semaphore_name):
        self.window.settings().erase(semaphore_name)

    def has_semaphore(self, semaphore_name):
        return self.window.settings().get(semaphore_name) == True

class RefreshBrowserViewCommand(sublime_plugin.WindowCommand):
    def run(self):
        window = sublime.active_window()
        views = []
        view = self.open_new_view(window, 1, 'PassManager')
        views.append(view)
        if( self.get_use_loading() == True ):
            window.focus_view(view)
            updatingview = window.new_file()
            updatingview.run_command("open_updating")
        thread = PassManagerBrowserFiller(views)
        thread.start()

    def open_new_view(self, window, group, name):
        window.focus_group(group)
        view = window.new_file()
        view.set_scratch(True)
        view.set_name(name)
        view.set_read_only(False)
        return view

    def get_use_loading(self):
        settings = sublime.load_settings('PassManager.sublime-settings')
        use_loading = settings.get('use_loading') or False
        if( isinstance(use_loading, bool) ):
            return use_loading
        return False

class PassManagerBrowserFiller(threading.Thread):
    def __init__(self, views):
        threading.Thread.__init__(self)
        self.views = views

    def run(self):
        if(len(self.views) == 1):
            self.views[0].run_command("fill_browser_view", { "args": {"group": 1} })
        else:
            sublime.status_message('No views to fill!!')

class FillBrowserViewCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        self.utils = _passManagerUtils()
        self.view = view

    def run(self, edit, args):
        group = args.get('group') or 1
        classname = args.get('classname') or None
        view = self.view
        # remove view content if present
        viewcontent = sublime.Region(0,view.size())
        view.erase(edit,viewcontent)
        self._fill_passwords(view, edit)
        self.utils.close_all_updating();

    def _fill_passwords(self, view, edit):
        view.set_read_only(False)
        viewcontent = sublime.Region(0,view.size())
        view.erase(edit,viewcontent)
        regions = []
        numregions = 0
        passwords = self.utils._scandir(self.utils.get_pass_storage())
        regions = self._r_pass2edit(view, edit, passwords, 0);
        view.add_regions('passmanagerbrowser' , regions, 'passmanagerbrowser', 'bookmark',sublime.DRAW_OUTLINED)
        view.settings().set('numregions', len(regions))
        view.end_edit(edit)
        view.set_read_only(True)

    def _r_pass2edit(self, view, edit, password, level = 0, path = '/'):
        regions = []
        spaces = (" " * level)
        for directory in password['dirs'].keys():
            view.insert(edit, view.size(),'\n')
            view.insert(edit, view.size(), spaces + directory)
            regions.extend(self._r_pass2edit(view, edit, password['dirs'][directory], level + 1, path + directory + '/' ))
        for file in password['files']:
            view.insert(edit, view.size(),'\n' + spaces)
            initregion = view.size()
            view.insert(edit, view.size(), file.strip('.gpg'))
            endregion = view.size()
            regions.append(sublime.Region(initregion,endregion))
            rp = view.window().settings().get('regions-paths') or {}
            rp.update( { str(initregion)+':'+str(endregion) : path + file } )
            view.window().settings().set('regions-paths', rp)
        return regions

class WriteViewCommand(sublime_plugin.TextCommand):
    def run(self, edit, args):
      text=args.get('text')
      self.view.insert(edit, self.view.size(), text)

class PassManagerOpenLayoutCommand(sublime_plugin.WindowCommand):
    def __init__(self, args):
        self.utils = _passManagerUtils()
        self.utils.del_semaphore('on_selection_modified')

    def run(self):
        window = sublime.active_window()
        browser_view = self.utils.find_browser_view()
        if( browser_view != None ):
            browser_view.run_command("refresh_browser_view", { } )
            return
        oldlayout = window.get_layout()
        settings = sublime.load_settings('pass_manager.sublime-settings')
        settings.set('php_class_browser_revert_layout',oldlayout)
        sublime.save_settings('pass_manager.settings')
        layout = self.get_layout_config()
        window.set_layout(layout)
        window.run_command("refresh_browser_view", { } )

    def get_layout_config(self):
        settings = sublime.load_settings('PassManager.sublime-settings')
        one_panel_layout = settings.get('one_panel_layout') or None
        try:
          if( one_panel_layout != None and len( one_panel_layout.get('cells') ) == 2):
            return one_panel_layout
        except:
          pass

        #one panel default
        return {
          'cols': [0.0, 0.65, 1.0], 
          'cells': [[0, 0, 1, 1], [1, 0, 2, 1]], 
          'rows': [0.0, 1.0]
        }

class PassManagerCloseLayoutCommand(sublime_plugin.WindowCommand):
    def __init__(self, args):
        self.utils = _passManagerUtils()
        self.utils.del_semaphore('on_selection_modified')

    def run(self):
        window = sublime.active_window()
        settings = sublime.load_settings('pass_manager.sublime-settings')
        oldlayout = settings.get('php_class_browser_revert_layout')
        if( oldlayout != None ):
            window.set_layout(oldlayout)
        else:
            window.set_layout({
                "cols": [0.0, 1.0],
                "rows": [0, 1],
                "cells": [[0, 0, 1, 1]]
            })
        self.utils.close_all_updating()
        browser_view = self.utils.find_browser_view()
        if( browser_view != None ):
            window.focus_view(browser_view)
            window.run_command('close')
        window.focus_group(0)

class ClickPassmanagerBrowserCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        self.utils = _passManagerUtils()
        self.view = view

    def run(self, edit, args):
        password_path = args.get('path')
        password = self.utils.get_password(password_path)
        sublime.set_clipboard(password)
        sublime.status_message('password value copied to clipboard')
        self.utils.del_semaphore('on_selection_modified')

class PassManagerPaletteCommand(sublime_plugin.WindowCommand):
  def __init__(self, window):
      self.window = window
      self.utils = _passManagerUtils()
      self.options = self.utils._scandir(self.utils.get_pass_storage())
      self.currentpath = ""

  def on_done(self, index):
      if index >= 0:
          selected = self.getLevel(self.currentpath)[index];
          if ( selected == '..' or self.getLevel(self.currentpath+'/'+selected)):
              if (selected == '..'):
                  parts = self.currentpath.split('/')
                  if (len(parts)):
                    parts.pop()
                    self.currentpath = '/'.join(parts)
              else:
                  self.currentpath = self.currentpath+'/'+selected
              sublime.active_window().show_quick_panel(self.getLevel(self.currentpath), self.on_done)
          else:
              view = self.window.active_view()
              view.run_command('write_view',{'args': {'text': self.utils.get_password(self.currentpath + '/' + selected) } })
              self.currentpath = ''

  def run(self):
      sublime.active_window().show_quick_panel(self.getLevel(self.currentpath), self.on_done)

  def getLevel(self, path):
      arr=self.options
      parts=path.split("/")
      for part in parts:
          if len(part) > 0:
              try:
                  arr = arr['dirs'][part]
              except:
                  return False
      out = []
      if(path != ''):
          out.append('..')
      out.extend(arr['dirs'].keys())
      for file in arr['files']:
        out.append(file.rstrip('.gpg'))
      return out

class PassManager(sublime_plugin.EventListener):
    def on_selection_modified(self, view):
        window = sublime.active_window()
        if( window == None ):
            return

        utils = _passManagerUtils()
        if( utils.is_browser_view(view) != True ):
            return

        rp = view.window().settings().get('regions-paths')
        regions = view.get_regions('passmanagerbrowser')

        point = view.sel()[0]
        if(point.begin() == point.end()):
            return

        if(utils.has_semaphore('on_selection_modified')):
          return;
        utils.add_semaphore('on_selection_modified')

        selection = view.line(point)
        for region in regions:
          if (selection.contains(region)):
            word = rp.get( str(region.begin())+':'+str(region.end()) ).rstrip('.gpg')
            window.run_command("click_passmanager_browser",{'args':{ 'path': word}})
