// Seeed XIAO ESP32S3: enable native USB CDC on boot. No protocol/debug text here.
#include <Arduino.h>

struct Pending {
  uint8_t bytes[256];
  size_t used = 0;
  size_t sent = 0;
};
Pending toFpga, toHost;

template <typename Source, typename Sink>
void forwardBytes(Source &source, Sink &sink, Pending &pending) {
  if (pending.sent == pending.used) {
    pending.sent = pending.used = 0;
    while (source.available() && pending.used < sizeof(pending.bytes)) {
      int value = source.read();
      if (value < 0) break;
      pending.bytes[pending.used++] = static_cast<uint8_t>(value);
    }
  }
  int room = sink.availableForWrite();
  if (room > 0 && pending.sent < pending.used) {
    size_t count = min(static_cast<size_t>(room), pending.used - pending.sent);
    pending.sent += sink.write(pending.bytes + pending.sent, count);
  }
}

void setup() {
  Serial.begin(115200);
  Serial1.setRxBufferSize(2048);
  Serial1.begin(115200, SERIAL_8N1, 44, 43);
}

void loop() {
  // Keep draining UART even if USB is absent; bounded loss is recovered by host status.
  if (Serial) {
    forwardBytes(Serial, Serial1, toFpga);
    forwardBytes(Serial1, Serial, toHost);
  } else {
    toFpga.used = toFpga.sent = 0;
    while (Serial.available()) Serial.read();
    toHost.used = toHost.sent = 0;
    while (Serial1.available()) Serial1.read();
  }
  yield();
}
