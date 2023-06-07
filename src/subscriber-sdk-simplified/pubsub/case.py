
import re


def pascal_to_kebab_case(s):
	# explain regex:
	# (?<!^) - negative lookbehind, don't match the start of the string
	# (?=[A-Z]) - positive lookahead, match any uppercase letter
	# so this matches any uppercase letter that is not at the start of the string
	# and inserts a dash before it
	return re.sub(r"(?<!^)(?=[A-Z])", "-", s).lower()

def snake_to_kebab_case(s):
	return s.replace("_", "-")