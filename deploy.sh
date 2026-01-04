docker stop $(docker ps -a | grep forum | awk '{print $1}' | awk '(NR==1)')
docker rm $(docker ps -a | grep forum | awk '{print $1}' | awk '(NR==1)')
docker image rm $(docker images | grep forum | awk '{print $3}' | awk '(NR==1)')
docker-compose up
