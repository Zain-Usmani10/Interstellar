// sequencer.v
// The mission itself: the active plan, the mission state, the tick counter,
// the fuel ledger and the two burn events.
//
// The plan is seven numbers from the laptop:
//   mission_id, departure_tick, arrival_tick, end_tick,
//   initial_fuel_g, departure_fuel_g, capture_fuel_g
//
// States (same numbers as on the wire):
//   0 IDLE  1 LOADED  2 ARMED  3 RUNNING  4 SAFE  5 COMPLETE  6 ABORTED
//
// What happens while RUNNING, once per 100 Hz tick:
//   - tick_count goes up by 1.
//   - When tick_count reaches departure_tick: subtract departure_fuel_g,
//     set mask bit 0, remember the tick. Fires once.
//   - When tick_count reaches arrival_tick (and departure is done):
//     subtract capture_fuel_g, set mask bit 1, remember the tick, COMPLETE.
//   - If a burn costs more fuel than is left: no burn, state SAFE.
//
// The clock keeps counting in SAFE and ABORTED until end_tick (the
// spacecraft keeps coasting). COMPLETE and CLEAR stop it.
//
// The do_* inputs are one-clock pulses from cmd_handler, which has already
// checked that each command is allowed. This module just applies them.

module sequencer (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        tick,               // mission 100 Hz enable

    // checked commands from cmd_handler
    input  wire        do_commit,          // activate the staged plan
    input  wire        do_arm,
    input  wire        do_start,
    input  wire        do_abort,
    input  wire        do_clear,

    // staged plan, copied on do_commit
    input  wire [31:0] staged_mission_id,
    input  wire [31:0] staged_departure_tick,
    input  wire [31:0] staged_arrival_tick,
    input  wire [31:0] staged_end_tick,
    input  wire [31:0] staged_initial_fuel_g,
    input  wire [31:0] staged_departure_fuel_g,
    input  wire [31:0] staged_capture_fuel_g,
    input  wire [15:0] staged_crc16,

    // mission status
    output reg         plan_valid,         // a plan is active
    output reg  [31:0] mission_id,         // 0 when no plan
    output reg  [15:0] plan_crc16,         // 0 when no plan
    output reg  [2:0]  state,
    output reg  [31:0] tick_count,
    output reg  [1:0]  executed_mask,      // bit 0 departure, bit 1 capture
    output reg  [31:0] fuel_g,
    output reg  [31:0] departure_executed_tick,   // FFFFFFFF = not yet
    output reg  [31:0] capture_executed_tick,     // FFFFFFFF = not yet
    output reg  [2:0]  safe_reason,        // 0 none, 3 fuel

    output reg         tick_restart,       // restarts the mission tick divider
    output reg         changed             // pulse: state or events changed
);

    localparam [2:0] ST_IDLE     = 3'd0,
                     ST_LOADED   = 3'd1,
                     ST_ARMED    = 3'd2,
                     ST_RUNNING  = 3'd3,
                     ST_SAFE     = 3'd4,
                     ST_COMPLETE = 3'd5,
                     ST_ABORTED  = 3'd6;

    localparam [2:0]  SAFE_NONE = 3'd0,
                      SAFE_FUEL = 3'd3;
    localparam [31:0] UNSET     = 32'hFFFF_FFFF;

    // Active plan.
    reg [31:0] departure_tick;
    reg [31:0] arrival_tick;
    reg [31:0] end_tick;
    reg [31:0] departure_fuel_g;
    reg [31:0] capture_fuel_g;

    reg        clock_running;      // mission clock latch (set by START)

    wire [31:0] next_tick = tick_count + 32'd1;
    wire        step      = tick && clock_running;

    // A burn is due on this tick. Commands that stop the mission win.
    wire burn_allowed  = step && (state == ST_RUNNING) && !do_abort && !do_clear;
    wire departure_due = burn_allowed && !executed_mask[0] && (next_tick >= departure_tick);
    wire capture_due   = burn_allowed && (executed_mask == 2'b01) && (next_tick >= arrival_tick);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            plan_valid              <= 1'b0;
            mission_id              <= 32'd0;
            plan_crc16              <= 16'd0;
            departure_tick          <= 32'd0;
            arrival_tick            <= 32'd0;
            end_tick                <= 32'd0;
            departure_fuel_g        <= 32'd0;
            capture_fuel_g          <= 32'd0;
            state                   <= ST_IDLE;
            tick_count              <= 32'd0;
            executed_mask           <= 2'b00;
            fuel_g                  <= 32'd0;
            departure_executed_tick <= UNSET;
            capture_executed_tick   <= UNSET;
            safe_reason             <= SAFE_NONE;
            clock_running           <= 1'b0;
            tick_restart            <= 1'b0;
            changed                 <= 1'b0;
        end else begin
            tick_restart <= 1'b0;
            changed      <= 1'b0;

            // ---- 1. Mission time. Stops at end_tick.
            if (step) begin
                tick_count <= next_tick;
                if (next_tick >= end_tick)
                    clock_running <= 1'b0;
            end

            // ---- 2. Scheduled burns.
            if (departure_due) begin
                changed <= 1'b1;
                if (departure_fuel_g > fuel_g) begin
                    state       <= ST_SAFE;
                    safe_reason <= SAFE_FUEL;
                end else begin
                    fuel_g                  <= fuel_g - departure_fuel_g;
                    executed_mask[0]        <= 1'b1;
                    departure_executed_tick <= next_tick;
                end
            end else if (capture_due) begin
                changed <= 1'b1;
                if (capture_fuel_g > fuel_g) begin
                    state       <= ST_SAFE;
                    safe_reason <= SAFE_FUEL;
                end else begin
                    fuel_g                <= fuel_g - capture_fuel_g;
                    executed_mask[1]      <= 1'b1;
                    capture_executed_tick <= next_tick;
                    state                 <= ST_COMPLETE;
                    clock_running         <= 1'b0;     // mission ends here
                end
            end

            // ---- 3. Commands. Written last, so they win over the above.
            if (do_commit) begin
                plan_valid              <= 1'b1;
                mission_id              <= staged_mission_id;
                plan_crc16              <= staged_crc16;
                departure_tick          <= staged_departure_tick;
                arrival_tick            <= staged_arrival_tick;
                end_tick                <= staged_end_tick;
                departure_fuel_g        <= staged_departure_fuel_g;
                capture_fuel_g          <= staged_capture_fuel_g;
                fuel_g                  <= staged_initial_fuel_g;
                state                   <= ST_LOADED;
                tick_count              <= 32'd0;
                executed_mask           <= 2'b00;
                departure_executed_tick <= UNSET;
                capture_executed_tick   <= UNSET;
                safe_reason             <= SAFE_NONE;
                changed                 <= 1'b1;
            end

            if (do_arm) begin
                state   <= ST_ARMED;
                changed <= 1'b1;
            end

            if (do_start) begin
                state         <= ST_RUNNING;
                tick_count    <= 32'd0;
                clock_running <= 1'b1;
                tick_restart  <= 1'b1;       // first tick is one full period away
                changed       <= 1'b1;
            end

            if (do_abort) begin
                state   <= ST_ABORTED;       // clock keeps running to end_tick
                changed <= 1'b1;
            end

            if (do_clear) begin
                plan_valid              <= 1'b0;
                mission_id              <= 32'd0;
                plan_crc16              <= 16'd0;
                state                   <= ST_IDLE;
                tick_count              <= 32'd0;
                executed_mask           <= 2'b00;
                fuel_g                  <= 32'd0;
                departure_executed_tick <= UNSET;
                capture_executed_tick   <= UNSET;
                safe_reason             <= SAFE_NONE;
                clock_running           <= 1'b0;
                changed                 <= 1'b1;
            end
        end
    end

endmodule
