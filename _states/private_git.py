#!/usr/bin/env python
'''
Support to pull private git repository
'''
# Import python libs
import os
import logging

# Import salt libs
import salt.utils
from salt.exceptions import SaltException

log = logging.getLogger(__name__)

def present(
  name,
  target,
  deploy_key,
  runas='root',
  deploy_port=22,
  revision="master"
  ):
  """Pull a private repository"""
  ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
  _make_target_directory_if_necessary(os.path.dirname(target), user=runas, group=runas, mode=644)
  git_deploy_wrapper_file = _make_deploy_key(target, deploy_key, deploy_port=deploy_port, user=runas, group=runas)
  _clone_repo(name, target, git_deploy_wrapper_file, user=runas)
  ret['result'] = True
  return ret
  

def _make_target_directory_if_necessary(dir_to_create, user='root', group='root', mode=644):
  """Make the base directory to clone the repo"""
  if not __salt__['file.directory_exists'](dir_to_create):
    log.debug(
      """
        ---- Creating directory ----
        {dir} ({mode})
      """.format(dir=dir_to_create, mode=mode)
    )
    # check user
    __salt__['file.makedirs_perms'](dir_to_create,
     user=user,
     group=group,
     mode=mode
    )

def _make_deploy_key(target, deploy_key, user='deploy', group='deploy', deploy_port=22):
  """docstring for _make_deploy_key"""
  
  target_dir = os.path.dirname(target)
  deploy_key_file = os.path.join(target_dir, 'id_deploy')
  git_deploy_wrapper_file = os.path.join(target_dir, 'git_deploy_wrapper.sh')
  
  if not __salt__['file.file_exists'](deploy_key_file):      
    _handle_salt_template(deploy_key_file,
        'salt://states_templates/id_deploy',
        600,
        user=user, 
        group=group, 
        defaults={'deploy_key': deploy_key})
  
  if not __salt__['file.file_exists'](git_deploy_wrapper_file):
    defaults = {'id_deploy': deploy_key_file, 'port': deploy_port}
    _handle_salt_template(git_deploy_wrapper_file, 'salt://states_templates/git_deploy_wrapper', 755, defaults=defaults)
  
  return git_deploy_wrapper_file
    

def _clone_repo(repo, target, git_deploy_wrapper_file, user='root'):
  """docstring for _clone_repo"""
  
  log.debug("Cloning the repo %s to directory %s" % (repo, target))
  cmd_kwargs = {'cwd': '/tmp', 'runas': user}
  user = cmd_kwargs.get('user', user)
  environ = "GIT_SSH={git_ssh}".format(git_ssh=git_deploy_wrapper_file)
  
  if not __salt__['file.file_exists'](target):
    cmd = "{environ} git clone --depth=5 {repo} {target}".format(repo=repo, target=target, environ=environ)
    return __salt__['cmd.run'](cmd, **cmd_kwargs)
  
def _handle_salt_template(path, source, mode, env=None, user='root', group='root', defaults={}, **kwargs):
  template = 'jinja'
  backup = ''
  
  if env is None:
    env = kwargs.get('__env__', 'base')
  else:
    env = env
  
  log.debug("""
    --- env ---
    env: {env}
  """.format(env=env)
  )
  source, source_hash = __salt__['file.source_list'](source,'',env)
  log.debug(
    """--- source_list 
    source: {source}
    source_hash: {source_hash}
    """.format(source=source, source_hash=source_hash)
  )
  sfn, source_sum, comment = __salt__['file.get_managed'](path,
    template,
    source,
    source_hash,
    user,
    group,
    mode,
    env,
    defaults,
    {})
  ret = {'name': path, 'result': None, 'comment': '', 'changes': {}}
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
      """.format(path=path, sfn=sfn, ret=ret, source=source, source_sum=source_sum, user=user, group=group, mode=mode, env=env, backup=backup, source_hash=source_hash,
        defaults=defaults,comment=comment)
    )
    ret = __salt__['file.manage_file'](path, sfn, ret, source, source_sum, user, group, mode, env, backup)
    log.debug("""ret for manage_file: {ret}""".format(ret=ret))
  except Exception, e:
    log.error("Something went wrong :( {comment} / {exception}".format(comment=ret['comment'], exception=e))
    raise e
  
  return ret