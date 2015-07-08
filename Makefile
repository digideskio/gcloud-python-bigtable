GENERATED_DIR=$(shell pwd)/generated_python
FINAL_DIR="gcloud_bigtable/_generated"

help:
	@echo 'Makefile for a gcloud-python-bigtable                  '
	@echo '                                                       '
	@echo '   make generate         Generates the protobuf modules'
	@echo '   make check_generate   Checks that generate succeeded'
	@echo '   make clean            Clean generated files         '

generate:
	[ -d cloud-bigtable-client ] || git clone https://github.com/GoogleCloudPlatform/cloud-bigtable-client
	cd cloud-bigtable-client && git pull origin master
	mkdir -p $(GENERATED_DIR)
	cd cloud-bigtable-client/bigtable-protos/src/main/proto && \
	    protoc google/bigtable/v1/*.proto --python_out=$(GENERATED_DIR)
	mv $(GENERATED_DIR)/google/bigtable/v1/* $(FINAL_DIR)
	cd cloud-bigtable-client/bigtable-protos/src/main/proto && \
	    protoc google/api/*.proto --python_out=$(GENERATED_DIR)
	mv $(GENERATED_DIR)/google/api/* $(FINAL_DIR)
	cd cloud-bigtable-client/bigtable-protos/src/main/proto && \
	    protoc google/protobuf/empty.proto --python_out=$(GENERATED_DIR)
	mv $(GENERATED_DIR)/google/protobuf/empty_pb2.py $(FINAL_DIR)
	python scripts/rewrite_imports.py

check_generate:
	python -c "import gcloud_bigtable._generated"
	python -c "from gcloud_bigtable._generated import annotations_pb2"
	python -c "from gcloud_bigtable._generated import bigtable_data_pb2"
	python -c "from gcloud_bigtable._generated import bigtable_service_messages_pb2"
	python -c "from gcloud_bigtable._generated import bigtable_service_pb2"
	python -c "from gcloud_bigtable._generated import empty_pb2"
	python -c "from gcloud_bigtable._generated import http_pb2"

clean:
	rm -fr cloud-bigtable-client $(GENERATED_DIR)

.PHONY: generate check_generate clean
