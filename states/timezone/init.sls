/etc/timezone:
	file.append:
		- text: {{ pillar.get('timezone', 'US/Pacific') }}
	cmd.wait:
		- cwd: /etc
		- name: dpkg-reconfigure --frontend noninteractive tzdata
		- watch:
			- file: /etc/timezone
