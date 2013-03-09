/etc/timezone:
	file.append:
		- text: {{ pillar['timezone'] }}
	cmd.wait:
		- cwd: /etc
		- name: dpkg-reconfigure --frontend noninteractive tzdata
		- watch:
			- file: /etc/timezone
