docker_build:
	docker build -t ramaro/tesoro .

docker_push:
	docker push ramaro/tesoro

all: docker_build docker_push
