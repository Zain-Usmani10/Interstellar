// status_gen.v
// Builds the 40-byte STATUS payload and asks frame_tx to send it.
//
// A STATUS is sent:
//   - when send_req pulses (a DISCOVER or GET_STATUS arrived, or the
//     mission state or a burn event just changed), and
//   - every PERIOD_TICKS ticks of the 100 Hz tick (default 10 = 10 Hz).
// If the transmitter is busy the request waits until it is free. Several
// requests while waiting become one STATUS; nothing is lost because the
// event flags and ticks in it are permanent.
//
// Each STATUS carries the board's own telemetry sequence number, which
// starts at 0 after reset and goes up by 1 per STATUS sent.
//
// STATUS payload, little-endian, in this order:
//   mission_id(4) tick(4) state(1) executed_mask(1) safe_reason(1) 0(1)
//   fuel_remaining_g(4) departure_executed_tick(4) capture_executed_tick(4)
//   masked_fault_count(4) no_majority_count(4) rx_error_count(4)
//   plan_crc16(2) 0(2)

module status_gen #(
    parameter integer PERIOD_TICKS = 10
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         send_req,           // one-clock pulse
    input  wire         period_tick,        // free-running 100 Hz enable
    input  wire         tx_free,            // frame_tx can take a frame now
    // values to report
    input  wire [31:0]  mission_id,
    input  wire [31:0]  tick,
    input  wire [7:0]   state,
    input  wire [7:0]   executed_mask,
    input  wire [7:0]   safe_reason,
    input  wire [31:0]  fuel_remaining_g,
    input  wire [31:0]  departure_executed_tick,
    input  wire [31:0]  capture_executed_tick,
    input  wire [31:0]  masked_fault_count,
    input  wire [31:0]  no_majority_count,
    input  wire [31:0]  rx_error_count,
    input  wire [15:0]  plan_crc16,
    // to frame_tx
    output reg          tx_start,
    output wire [7:0]   tx_type,
    output wire [15:0]  tx_seq,
    output wire [319:0] tx_payload,
    output wire [7:0]   tx_len,
    output wire         pending             // a STATUS is waiting to be sent
);

    reg        want;
    reg [15:0] telemetry_seq;
    reg [7:0]  period_count;

    wire period_due = period_tick && (period_count == PERIOD_TICKS - 1);
    wire request    = send_req || period_due;

    assign pending = want;
    assign tx_type = 8'h81;
    assign tx_len  = 8'd40;
    assign tx_seq  = telemetry_seq;

    // Byte 0 of the payload is bits [7:0], so the first field is written last.
    assign tx_payload = {
        16'h0000,
        plan_crc16,
        rx_error_count,
        no_majority_count,
        masked_fault_count,
        capture_executed_tick,
        departure_executed_tick,
        fuel_remaining_g,
        8'h00,
        safe_reason,
        executed_mask,
        state,
        tick,
        mission_id
    };

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            want          <= 1'b0;
            tx_start      <= 1'b0;
            telemetry_seq <= 16'd0;
            period_count  <= 8'd0;
        end else begin
            tx_start <= 1'b0;

            // Sequence moves on the clock after the frame was handed over,
            // so the frame that just started still carries the old value.
            if (tx_start)
                telemetry_seq <= telemetry_seq + 16'd1;

            if (period_tick)
                period_count <= period_due ? 8'd0 : period_count + 8'd1;

            if (request)
                want <= 1'b1;

            if (want && tx_free && !tx_start) begin
                tx_start <= 1'b1;
                want     <= request;       // keep a request that arrives right now
            end
        end
    end

endmodule
