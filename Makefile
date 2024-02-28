coverage:
	python -W ignore -m coverage run -m unittest discover -s oxn/tests/

build:
	python -m build

clean:
	rm -rf build/ && rm -rf dist/ && rm -rf oxn.egg-info/
	
