/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name input \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name input \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name output \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name output \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name review \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name review \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name intake \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name intake \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name structured \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name structured \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name cleared \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name cleared \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name ready \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name ready \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name support \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name support \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name finance \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name finance \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name website \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name website \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name sales \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name sales \
  --delete-config retention.ms

/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name outflow \
  --add-config retention.ms=1000
sleep 2
/opt/homebrew/bin/kafka-configs --bootstrap-server localhost:9092 \
  --alter --entity-type topics --entity-name outflow \
  --delete-config retention.ms
