// trip_clock.v
// Days-to-arrival counter for the cockpit display.
//
// The control station tells the shuttle how many days the planned trip
// (departure tick to arrival tick) stands for: SET_TRIP_DAYS. From that and
// the tick counter this module keeps "days to arrival".
//
// The exact rule, which the control station also uses:
//   trip_ticks   = arrival_tick - departure_tick
//   elapsed_days = floor((tick - departure_tick) * trip_days / trip_ticks)
//                  (0 before departure, trip_days from the arrival tick on)
//   days_to_arrival = trip_days - elapsed_days
//
// No divider is needed. On every tick between departure and arrival we add
// trip_days to an accumulator. Whenever the accumulator has reached
// trip_ticks we subtract trip_ticks and count one more elapsed day (one
// subtraction per clock; there are 500,000 clocks between ticks).
//
// Display only. Nothing here can change the mission or the burns.

module trip_clock (
    input  wire        clk,
    input  wire        rst_n,

    // plan events (same pulses the sequencer gets)
    input  wire        do_commit,
    input  wire [31:0] staged_departure_tick,
    input  wire [31:0] staged_arrival_tick,
    input  wire        do_start,
    input  wire        do_clear,

    // SET_TRIP_DAYS, already checked by cmd_handler
    input  wire        do_set_days,
    input  wire [31:0] set_days_value,

    input  wire [31:0] tick_count,         // mission tick counter

    output reg         trip_days_valid,    // SET_TRIP_DAYS was received
    output reg  [31:0] trip_days,
    output wire [31:0] days_to_arrival,
    output reg  [31:0] departure_tick      // active plan's departure tick
);

    reg [31:0] arrival_tick;
    reg [31:0] trip_ticks;
    reg [31:0] elapsed_days;
    reg [31:0] acc;
    reg [31:0] prev_tick;

    assign days_to_arrival = trip_days - elapsed_days;

    // The tick counter just moved to a tick inside the trip.
    wire tick_advanced = (tick_count != prev_tick);
    wire in_trip       = (tick_count > departure_tick) && (tick_count <= arrival_tick);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            trip_days_valid <= 1'b0;
            trip_days       <= 32'd0;
            departure_tick  <= 32'd0;
            arrival_tick    <= 32'd0;
            trip_ticks      <= 32'd0;
            elapsed_days    <= 32'd0;
            acc             <= 32'd0;
            prev_tick       <= 32'd0;
        end else begin
            prev_tick <= tick_count;

            if (trip_days_valid && tick_advanced && in_trip) begin
                acc <= acc + trip_days;
            end else if (trip_days_valid && acc >= trip_ticks && trip_ticks != 32'd0) begin
                acc          <= acc - trip_ticks;
                elapsed_days <= elapsed_days + 32'd1;
            end

            // A new plan or a cleared plan forgets the trip length.
            if (do_commit) begin
                departure_tick  <= staged_departure_tick;
                arrival_tick    <= staged_arrival_tick;
                trip_ticks      <= staged_arrival_tick - staged_departure_tick;
                trip_days_valid <= 1'b0;
                trip_days       <= 32'd0;
                elapsed_days    <= 32'd0;
                acc             <= 32'd0;
            end

            if (do_clear) begin
                trip_days_valid <= 1'b0;
                trip_days       <= 32'd0;
                elapsed_days    <= 32'd0;
                acc             <= 32'd0;
            end

            if (do_set_days) begin
                trip_days_valid <= 1'b1;
                trip_days       <= set_days_value;
                elapsed_days    <= 32'd0;
                acc             <= 32'd0;
            end

            if (do_start) begin
                elapsed_days <= 32'd0;
                acc          <= 32'd0;
            end
        end
    end

endmodule
