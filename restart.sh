brew services stop kafka
brew services stop zookeeper
brew services list
echo "stopped"
brew services start zookeeper
brew services start kafka
echo "wait for start"
brew services list