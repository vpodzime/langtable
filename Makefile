DESTDIR=/usr
DATADIR=$(DESTDIR)/share/langtable
DEBUG=
PWD := $(shell pwd)
SRCDIR=$(PWD)

vala-bin:
	valac --pkg=libxml-2.0 --pkg=gee-0.8 --thread --target-glib=2.32 langtable.vala

vala-lib:
	valac -X -fPIC -X -shared --pkg=libxml-2.0 --pkg=gee-0.8 --thread --target-glib=2.32 \
		--library=liblangtable --gir=langtable-0.1.gir -H langtable.h -o liblangtable.so langtable.vala
	g-ir-compiler --shared-library=liblangtable.so --output=langtable-0.1.typelib langtable-0.1.gir

install:
	perl -pi -e "s,_datadir = '(.*)',_datadir = '$(DATADIR)'," langtable.py
	DISTUTILS_DEBUG=$(DEBUG) python ./setup.py install --prefix=$(DESTDIR) --install-data=$(DATADIR)
	gzip --force --best $(DATADIR)/*.xml

.PHONY: test
test: install
	python langtable.py
	(cd $(DATADIR); python -m doctest $(SRCDIR)/test_cases.txt)
	xmllint --noout --relaxng $(DATADIR)/schemas/keyboards.rng $(DATADIR)/keyboards.xml.gz
	xmllint --noout --relaxng $(DATADIR)/schemas/languages.rng $(DATADIR)/languages.xml.gz
	xmllint --noout --relaxng $(DATADIR)/schemas/territories.rng $(DATADIR)/territories.xml.gz

.PHONY: dist
dist:
	DISTUTILS_DEBUG=$(DEBUG) python ./setup.py sdist

.PHONY: clean
clean:
	git clean -dxf

MOCK_CONFIG=fedora-rawhide-x86_64
.PHONY: mockbuild
mockbuild: dist
	mkdir -p ./mockbuild-results/
	mock --root $(MOCK_CONFIG) --buildsrpm --spec langtable.spec --sources ./dist/
	cp /var/lib/mock/$(MOCK_CONFIG)/result/* ./mockbuild-results
	mock --root $(MOCK_CONFIG) --rebuild ./mockbuild-results/*.src.rpm
	cp /var/lib/mock/$(MOCK_CONFIG)/result/* ./mockbuild-results

.PHONY: review
review: mockbuild
	cp *.spec ./mockbuild-results/
	(cd ./mockbuild-results/; fedora-review -n langtable -m $(MOCK_CONFIG) )

# .rnc files for editing with Emacs
# https://fedoraproject.org/wiki/How_to_use_Emacs_for_XML_editing
%.rnc: %.rng
	trang $< $@

rnc: schemas/keyboards.rnc schemas/languages.rnc schemas/territories.rnc
	cp schemas/*.rnc data/
