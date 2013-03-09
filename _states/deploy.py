#!/usr/bin/env python
'''
Support for deploying an application
'''
# Import python libs
import os
import argparse
import re
import logging
import tempfile
import shutil
from pwd import getpwnam
from grp import getgrnam

# Import salt libs
import salt.utils
from salt.exceptions import SaltException

log = logging.getLogger(__name__)

## This is the rails object
# For the time being, I'm just getting this working, but will need to 
# come back later and abstract this to handle multiple application types

class App(object):
  """Application deployment"""
  def __init__(self, opts):
    super(App, self).__init__()
    self.opts = opts
  
  def deploy(self):
    """Call deploy"""
    self.before_deploy()
    self.deploy_repo()
    self.after_deploy()
    
    self.before_migrate()
    self.migrate()
    self.after_migrate()
    
    self.before_launch()
    self.launch()
    self.after_launch()
    
  def launch(self):
    """Launch!"""
    pass

  
  def before_deploy(self):
    """Callback that gets called before the actual deploy"""
    pass
  
  def after_deploy(self):
    """Callback after the git repo is called"""
    pass
  
  def before_migrate(self):
    """Callback before the migration command is run"""
    pass
  
  def after_migrate(self):
    """Callback after the migration command is run"""
    pass
  
  def before_launch(self):
    """Callback before the application is setup to launch"""
    pass
  
  def after_launch(self):
    """Callback after the application has launched"""
    pass

class Rails(App):
  """Rails class"""
  def __init__(self, opts):
    super(Rails, self).__init__(opts)
    self.opts         = opts
    self.name         = opts['name']
    self.repo         = opts['repo']
    self.docroot      = opts['docroot']
    self.ruby_version = opts['ruby_version']
    self.server       = opts['server']
    self.database     = opts['database']
    self.ssl          = opts['ssl']
    self.user         = opts['user']
    self.group        = opts['group']
    self.rails_env    = opts['rails_env']
    self.deploy_key   = opts['deploy_key']
    self.deploy_port  = opts['deploy_port']
    self.revision     = opts['revision']
    self.symlinks     = opts['symlinks']
    self.config_templates = opts['config_templates']
    self.kwargs       = opts['kwargs']
    self.salt         = opts['salt']
    self.grains       = opts['grains']
    
    ## Don't mess with the rest
    self.release_path = os.path.join(self.docroot, 'releases')
    self.shared_path  = os.path.join(self.docroot, 'shared')
    self.current_path = os.path.join(self.docroot, 'current')
    
    self.deploy_key_file          = ''
    self.git_deploy_wrapper_file  = ''
    
    if opts['env'] is None:
      self.env = self.kwargs.get('__env__', 'base')
    else:
      self.env = opts['env']
      
  def deploy(self):
    """Deploy"""
    return super(Rails, self).deploy()
    
  def before_deploy(self):
    """Before deploy callback"""
    self._create_path_structure()
    self._create_config_templates()
    self._setup_ssl_if_necessary()
    
    self._install_rvm_if_necessary()
    
    if self.deploy_key:
      self._create_deploy_file()
      
  def deploy_repo(self):
    """Deploy the repo"""
    ## Get the current sha
    self.get_current_sha()
    
    if not self.has_been_pulled():
      ## Now we're going to actually pull the repo
      deploy_path = self.git_pull()
      log.debug("Cloned the repository to: %s" % deploy_path)
      self.get_current_sha()
    else:
      self.git_update()
      
  def before_migrate(self):
    """Before migrations"""
    self._create_database_yml()
    
    self._create_symlinks()
    self._run_bundle_install()
    
  def migrate(self):
    """Migrate"""
    log.debug("calling db:migrate")
    self._run_rake("db:migrate")
    
  def after_migrate(self):
    """Callback after migrations"""
    self._run_rake("assets:precompile")
  
  def before_launch(self):
    """Callback before launch"""
    #### Enhancement for the future: check what to serve 
    ## For now, just use unicorn
    log.debug("server: %s" % self.server)
    if self.server:
      log.debug("Setting up server")
      self._setup_webserver()
    
    self._link_to_current_dir()
    
  def after_launch(self):
    """Callback after launch"""
    pass
    
  ## Create the path structure at the docroot
  def _create_path_structure(self):
    """Create the basic shared path structure"""

    # Just in case, make the 
    if not os.path.isdir(self.docroot):
      log.debug("makedir_please: %s" % self.docroot)
      self.makedir_please(self.docroot)

    for dir in ['shared', 'releases']:
      d = os.path.join(self.docroot, dir)
      if not os.path.isdir(d):
        self.makedir_please(d)

    for dir in ['log', 'config', 'system', 'vendor_bundle', 'assets', 'sockets', 'tmp', 'tmp/pids']:
      d = os.path.join(self.shared_path, dir)
      if not os.path.isdir(d):
        self.makedir_please(d)
        
  def _setup_ssl_if_necessary(self):
    """Setup ssl if ssl has been set"""
    pass

  def _install_rvm_if_necessary(self):
    ## Now, let's do the before, thinkgs like symlinking
    # Make sure the ruby version is correct and available
    if not self.salt['rvm.is_installed']():
      self.salt['rvm.install']()

    rubies = self.salt['rvm.list'](runas=self.user)

    if not self.ruby_version in [r[1] for r in rubies ]:
      self.salt['rvm.install_ruby'](self.ruby_version)
      self.salt['rvm.set_default'](self.ruby_version)
      self._handle_salt_template('/etc/rvmrc', 'salt://states_templates/rvmrc', 644, {})
      # self._cmd("chown -R %s /usr/local/rvm" % self.user, {'user': 'root'})
      self.salt['rvm.gemset_create'](self.ruby_version, self.name, runas=self.user)
      self.salt['rvm.do'](self.ruby_version, 'gem install bundler --no-ri --no-rdoc')
    
  # Create a deploy key
  def _create_deploy_file(self):
    """
      Create a deploy file, if necessary
    """
    deploy_key_file = os.path.join(self.docroot, 'id_deploy')
    git_deploy_wrapper_file = os.path.join(self.docroot, 'git_deploy_wrapper.sh')

    self._handle_salt_template(deploy_key_file, 'salt://states_templates/id_deploy', 600, {'deploy_key': self.deploy_key})
    self.deploy_key_file = deploy_key_file

    # Now we'll create the git_deploy_wrapper
    source = 'salt://states_templates/git_deploy_wrapper'
    defaults = {'id_deploy': deploy_key_file, 'port': self.deploy_port}

    self._handle_salt_template(git_deploy_wrapper_file, source, 755, defaults)
     
    self.git_deploy_wrapper_file = git_deploy_wrapper_file
    return git_deploy_wrapper_file
      
  def _handle_salt_template(self, path, source, mode, defaults={}):
    template = 'jinja'
    backup = ''
    # source_hash = self.salt['file.get_hash'](path)
    # log.debug("""---- source_hash ----
    #   source_hash: {hash}
    # """.format(hash=source_hash))
    source, source_hash = self.salt['file.source_list'](source,'',self.env)
    sfn, source_sum, comment = self.salt['file.get_managed'](path,
      template,
      source,
      source_hash,
      self.user,
      self.group,
      mode,
      self.env,
      defaults,
      {})
    ret = {'name': self.name, 'result': None, 'comment': '', 'changes': {}}
    try:
      log.debug(
        """---- file.manage_file ----
          path: {path}
          sfn: {sfn}
          ret: {ret}
          source: {source}
          source_sum: {source_sum}
          source_hash: {source_hash}
          user: {user}
          group: {group}
          mode: {mode}
          env: {env}
          backup: {backup}
          comment: {comment}
        """.format(path=path, sfn=sfn, ret=ret, source=source, source_sum=source_sum, user=self.user, group=self.group, mode=mode, env=self.env, backup=backup, source_hash=source_hash,
          defaults=defaults,comment=comment)
      )
      ret = self.salt['file.manage_file'](path, sfn, ret, source, source_sum, self.user, self.group, mode, self.env, backup)
      log.debug("""ret for manage_file: {ret}""".format(ret=ret))
    except Exception, e:
      log.error("Something went wrong :( {comment} / {exception}".format(comment=ret['comment'], exception=e))
      raise e
    
    return ret
    
  def get_current_sha(self):
   """
   Get the current revision
   """
   cmd = r"GIT_SSH={git_ssh} git ls-remote {repo}".format(git_ssh=self.git_deploy_wrapper_file, repo=self.repo)
   lines = self.salt['cmd.run_stdout'](cmd, runas=self.user)
   log.debug("get_current_sha: %s" % lines)

   for line in lines.splitlines():
     sha, branch = line.split('\t')
     if self.revision in branch:
       self.sha = sha
       self.revision_path = os.path.join(self.release_path, sha)
       return sha

   return None

  def has_been_pulled(self):
    """
    Check to see if we've deployed this application already
    """
    if os.path.isdir(self.revision_path):
      return True
    else:
      return False

  def git_pull(self):
   """
     Pull the repository
   """

   release_path = os.path.join(self.release_path, self.sha)

   cmd = r"git clone --depth=5 {repo} {release_path}".format(
           repo=self.repo, 
           release_path=release_path
         )
   log.debug("Cloning the repo %s to directory %s" % (self.repo, release_path))
   cmd_kwargs = {'cwd': '/tmp', 'runas': self.user}
   res = self._cmd(cmd, **cmd_kwargs)

   if not res:
     log.error("Something went majorly wrong: %s" % res)
     raise Exception("Something went majorly wrong: %s" % res)
   else:
     # Successfully pulled the repo, if the revision is given
     cmd_kwargs['cwd'] = self.revision_path
     if self.revision != "master":
       log.debug("Checking out branch %s" % self.revision)
       cmd_ret = self._cmd("git checkout -b %s" % self.revision, **cmd_kwargs)
       
     self._cmd("git submodule update --init --recursive", **cmd_kwargs)
     
   return release_path
   
  def git_update(self):
    """Update the repo"""
    cmd = r"git pull origin {branch}".format(
      branch=self.revision
    )
      
  def _create_database_yml(self):
    defaults = {
      'db_name': self.database.get('name'),
      'db_user': self.database.get('user'),
      'db_password': self.database.get('password'),
      'db_host': self.database.get('host', 'localhost'),
      'db_adapter': self.database.get('adapter'),
      'db_pool': self.database.get('pool', 5),
      'db_reconnect': self.database.get('reconnect', 'false'),
      'rails_env': self.rails_env
    }
    config_path = os.path.join(self.shared_path, 'config')
    database_yml_path = os.path.join(config_path, 'database.yml')
    ret = self._handle_salt_template(database_yml_path, 'salt://states_templates/database.yml', 644, defaults)
   
  def _create_config_templates(self):
    config_path = os.path.join(self.shared_path, 'config')
    for c in self.config_templates:
      config                  = c.format(environment=self.grains['environment'])
      master_config_file_path = self.config_templates[c].format(environment=self.grains['environment'])
      
      defaults  = {'name': self.name}
      config_file_path = os.path.join(config_path, config)
      log.debug("%s type ------------------------> %s" % (c, config))
      log.debug("_create_config_template: %s / %s" % (config_file_path, master_config_file_path))
      self._handle_salt_template(config_file_path, master_config_file_path, 744, defaults)
  
  def _create_symlinks(self):
   """Create symlinks"""
   log.debug("---------------> Creating symlinks")
   for c in self.config_templates:
     config = c.format(environment=self.grains['environment'])
     config_file = os.path.join('config', config)
     self._create_shared_symlink(config_file, config_file)
   if self.symlinks:
     for shared, target in self.symlinks.items():
       self._create_shared_symlink(shared, target)
     return True
   else:
     return False
     
  def _create_shared_symlink(self, shared, target):
    """Create a symlink"""
    src  = os.path.join(self.shared_path, shared)
    dest = os.path.join(self.revision_path, target)
    log.debug('creating symlink -----------------> %s -> %s' % (src, dest))
    self._create_symlink(src, dest)
     
  def _create_symlink(self, src, dest):
    """Create a symlink"""
    # if the root directory is not a directory of the destination file, create it
    if not os.path.isdir(os.path.dirname(dest)):
      self.makedir_please(os.path.dirname(dest))

    # If the link exists, make sure it's the "right" link. If it's not, then blow it away
    if os.path.islink(dest):
      if not os.readlink(dest) == src:
        os.remove(dest)
    # If the dest is a file and not a link, blow it away
    elif os.path.isfile(dest):
      os.remove(dest)
    # If it's a directory and not a link, blow it away
    elif os.path.isdir(dest):
      shutil.rmtree(dest)
    # Make the symlink
    if os.path.exists(src) and not os.path.exists(dest):
      os.symlink(src, dest)
      self.salt['file.chown'](dest, self.user, self.group)
    

  def _run_bundle_install(self):
   """Run bundle install"""
   shared_vendored_path = os.path.join(self.shared_path, 'vendor_bundle')
   common_groups = ['development test']
   cmd = r"bundle install --path={path} --deployment --without {without}".format(path=shared_vendored_path, without=' '.join(common_groups))
   
   res = self._cmd(cmd)
   log.debug("Got... %s", res)

   return True
     
  def _setup_webserver(self):
    """Setup the webserver"""
    ## Install unicorn
    self.salt['rvm.do'](self.ruby_version, 'gem install unicorn --no-ri --no-rdoc')
    ## First check for a unicorn.rb in the app, otherwise create one
    # TODO: Allow unix sockets
    config_dir = os.path.join(self.shared_path, 'config')
    unicorn_config = os.path.join(config_dir, 'unicorn.rb')
    
    tmp_dir = os.path.join(self.revision_path, 'tmp')
    pid_dir = os.path.join(tmp_dir, 'pids')
    unicorn_pidfile = os.path.join(pid_dir, 'unicorn.pid')
    
    log.debug("Creating unicorn config at %s with %s" % (unicorn_config, self.server))
    defaults = {
      'docroot': self.revision_path,
      'worker_processes': self.salt['grains.item']('num_cpus'),
      'preload_app': 'true',
      'listen_ports': self.server['ports'],
      'backlog': self.server.get('backlog', '2048'),
      'pidfile': unicorn_pidfile,
      'logger': self.server.get('logger', None),
      'before_fork': self.server.get('before_fork', None),
      'after_fork': self.server.get('after_fork', None),
      'stderr_path': self.server.get('stderr_path', None),
      'stdout_path': self.server.get('stdout_path', None)
    }
    ret = self._handle_salt_template(unicorn_config, 'salt://states_templates/unicorn_rb', 644, defaults)
    log.info("ret: %s" % ret)
    
    self._create_shared_symlink("config/unicorn.rb", "config/unicorn.%s.rb" % self.rails_env)

  def _link_to_current_dir(self):
    """Link revision path to the current directory"""
    log.debug("Linking {revision_path} to {current_path}".format(revision_path=self.revision_path, current_path=self.current_path))
    self._create_symlink(self.revision_path, self.current_path)
   
  def _run_rake(self, cmd):
    """Run rake command"""
    
    if self._has_rake_command(cmd):
      self._cmd("bundle exec rake {cmd}".format(cmd=cmd))
    

  def _has_rake_command(self, cmd):
    """Check if a rake command is defined"""
    lines = self._cmd( r"bundle exec rake -T {cmd}".format(cmd=cmd) )
    try:
      for line in lines.splitlines():
        command, desc = line.split('#')
        search_str = "rake %s" % cmd
        if search_str in command:
          return True
    except Exception:
      log.error("FAILED checking for rake task: %s" % lines)
    return False

  def _error(self, ret, err_msg):
     ret['result'] = False
     ret['comment'] = err_msg
     log.debug(
       "Received an error!\n%s" % err_msg
     )
     return ret
     
  def makedir_please(self, dir_to_create, mode=0755):
     """Make the directory and chown"""
     log.debug(
       """
         ---- Creating directory ----
         {dir} ({mode})
       """.format(dir=dir_to_create, mode=mode)
     )
     # check user
     self.salt['file.makedirs_perms'](dir_to_create,
      user=self.user,
      group=self.group,
      mode=mode
     )
     # self.salt['file.directory'](dir_to_create, 
     #  user=self.user, 
     #  group=self.group, 
     #  recurse=True,
     #  mode=mode,
     #  makedirs=True,
     #  clean=False,
     #  require=[]
     #  )

  def _cmd(self, cmd, cwd=None, **cmd_kwargs):
   """
     Run a command
   """
   user = cmd_kwargs.get('user', self.user)
   environ = "HOME=/home/{user} RAILS_ENV={rails_env} GIT_SSH={git_ssh}".format(
     rails_env=self.rails_env, git_ssh=self.git_deploy_wrapper_file, user=user
   )
   if not cwd:
     try:
      cwd = self.revision_path
     except:
      cwd = '/tmp'
      
   cmd_kwargs = {'cwd': cwd, 'runas': user}
   set_rvm = "source \"/usr/local/rvm/scripts/rvm\";"
   cmd = r"{set_rvm} {environ} {cmd}".format(cmd=cmd, set_rvm=set_rvm, environ=environ)
   return self.salt['cmd.run'](cmd, **cmd_kwargs)
    
def rails(name, repo, docroot, 
          ruby_version='1.9.3-p194',
          database={},
          ssl={},
          server={},
          user='deploy', 
          group='deploy', 
          rails_env='development', 
          deploy_key=None, 
          deploy_port='22',
          revision="master", 
          symlinks={},
          config_templates={},
          env=None,
          **kwargs):
  """
    Deploy a rails application
    
    name
      The name of the application
      
    repo
      The git repository to pull the application from
      
    docroot
      The location for the deploy
      The deployment follows the capistrano deployment with the following files
        docroot/
          releases/
          shared/
          current/ # symlink to latest release
    
    ruby_version
      The version of ruby to use
    
    database
      The database object. This must have the following attributes:
        name
        host
        user
        password
        adapter
    
    server
      The webserver to use to serve the application
      Defaults to unicorn
        options:
          type: unicorn
          port: port
      
    user
      The user to deploy the application as
      
    group
      The group to deploy the application as
      
    rails_env
      The RAILS_ENV to deploy the rails application
      
    deploy_key
      If deploy_key is passed, then it will be used to check out the repo
      
    deploy_port
      If the deploy_port is passed, it will use this as a custom port for the repo
    
    revision
      The revision to check out the application
  """
  ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
      
  opts = {
    'name': name, 
    'repo': repo,
    'docroot': docroot,
    'ruby_version': ruby_version,
    'database': database,
    'ssl': ssl,
    'server': server,
    'user': user,
    'group': group,
    'rails_env': rails_env,
    'deploy_key': deploy_key,
    'deploy_port': deploy_port,
    'revision': revision,
    'symlinks': symlinks,
    'config_templates': config_templates,
    'env': env,
    'kwargs': kwargs,
    'salt': __salt__,
    'grains': __grains__
  }
  rails = Rails(opts)
  rails.deploy()
  ret['result'] = True
  ret['comment'] = 'Application successfully deployed'
  return ret