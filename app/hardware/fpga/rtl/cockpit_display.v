// cockpit_display.v
// The shuttle's cockpit readout on the six seven-segment displays.
//
// HEX5 HEX4 : the mission state as two letters
//     Id idle   Ld loaded   Ar armed   rn running
//     SF safe   Co complete Ab aborted
//   When the link to the control station is lost, these two digits
//   alternate with "nL" (no link) once per second.
//
// HEX3..HEX0 : a number
//     idle                                  ----
//     loaded / armed                        trip length in days (---- if not set)
//     running, before the departure burn    T-minus as SS.cc (seconds.hundredths)
//     after the departure burn              days to arrival
//       (mission seconds elapsed if the trip length was never set)
//
// Display only. Outputs are active low; bit 7 of each is the decimal point.

module cockpit_display (
    input  wire        clk,
    input  wire        rst_n,

    input  wire [2:0]  state,
    input  wire        departed,           // departure burn done (mask bit 0)
    input  wire [31:0] tick_count,
    input  wire [31:0] departure_tick,
    input  wire        trip_days_valid,
    input  wire [31:0] trip_days,
    input  wire [31:0] days_to_arrival,
    input  wire        link_lost,
    input  wire        blink,              // 1 Hz square wave (the heartbeat)

    output wire [7:0]  hex0,
    output wire [7:0]  hex1,
    output wire [7:0]  hex2,
    output wire [7:0]  hex3,
    output wire [7:0]  hex4,
    output wire [7:0]  hex5
);

    localparam [2:0] ST_IDLE     = 3'd0,
                     ST_LOADED   = 3'd1,
                     ST_ARMED    = 3'd2,
                     ST_RUNNING  = 3'd3,
                     ST_SAFE     = 3'd4,
                     ST_COMPLETE = 3'd5,
                     ST_ABORTED  = 3'd6;

    // seg7 symbol codes (see seg7.v)
    localparam [4:0] C_1 = 5'd1,  C_5 = 5'd5,
                     C_DASH = 5'd10, C_BLANK = 5'd11,
                     C_d = 5'd12, C_L = 5'd13, C_A = 5'd14, C_r = 5'd15,
                     C_n = 5'd16, C_F = 5'd17, C_C = 5'd18, C_o = 5'd19,
                     C_b = 5'd20;

    // ------------------------------------------------------------ what number to show
    localparam [1:0] N_DASHES = 2'd0,   // ----
                     N_LOW4   = 2'd1,   // lowest four digits
                     N_SS_CC  = 2'd2,   // lowest four digits with a point: SS.cc
                     N_HIGH4  = 2'd3;   // digits 5..2 (drops the hundredths)

    wire [31:0] countdown = (tick_count < departure_tick) ? (departure_tick - tick_count) : 32'd0;

    reg [1:0]  num_mode;
    reg [31:0] num_value;

    always @(*) begin
        num_mode  = N_DASHES;
        num_value = 32'd0;

        if (departed) begin
            if (trip_days_valid) begin
                num_mode  = N_LOW4;
                num_value = days_to_arrival;
            end else begin
                num_mode  = N_HIGH4;            // ticks / 100 = seconds
                num_value = tick_count;
            end
        end else if (state == ST_RUNNING) begin
            num_value = countdown;
            num_mode  = (countdown < 32'd10000) ? N_SS_CC : N_HIGH4;
        end else if ((state == ST_LOADED || state == ST_ARMED) && trip_days_valid) begin
            num_mode  = N_LOW4;
            num_value = trip_days;
        end
    end

    // The converter handles up to 999,999.
    wire [19:0] bcd_in = (num_value > 32'd999999) ? 20'd999999 : num_value[19:0];
    wire [23:0] bcd;

    bin2bcd u_bin2bcd (
        .clk   (clk),
        .rst_n (rst_n),
        .value (bcd_in),
        .bcd   (bcd)
    );

    reg [4:0] n3, n2, n1, n0;
    always @(*) begin
        case (num_mode)
            N_DASHES: begin
                n3 = C_DASH; n2 = C_DASH; n1 = C_DASH; n0 = C_DASH;
            end
            N_HIGH4: begin
                n3 = {1'b0, bcd[23:20]}; n2 = {1'b0, bcd[19:16]};
                n1 = {1'b0, bcd[15:12]}; n0 = {1'b0, bcd[11:8]};
            end
            default: begin                      // N_LOW4, N_SS_CC
                n3 = {1'b0, bcd[15:12]}; n2 = {1'b0, bcd[11:8]};
                n1 = {1'b0, bcd[7:4]};   n0 = {1'b0, bcd[3:0]};
            end
        endcase
    end

    // ------------------------------------------------------------ the two state letters
    reg [4:0] s5, s4;
    always @(*) begin
        case (state)
            ST_IDLE:     begin s5 = C_1; s4 = C_d; end   // Id
            ST_LOADED:   begin s5 = C_L; s4 = C_d; end   // Ld
            ST_ARMED:    begin s5 = C_A; s4 = C_r; end   // Ar
            ST_RUNNING:  begin s5 = C_r; s4 = C_n; end   // rn
            ST_SAFE:     begin s5 = C_5; s4 = C_F; end   // SF
            ST_COMPLETE: begin s5 = C_C; s4 = C_o; end   // Co
            ST_ABORTED:  begin s5 = C_A; s4 = C_b; end   // Ab
            default:     begin s5 = C_DASH; s4 = C_DASH; end
        endcase
        if (link_lost && blink) begin
            s5 = C_n;                                    // nL
            s4 = C_L;
        end
    end

    // ------------------------------------------------------------ segments
    wire [6:0] g0, g1, g2, g3, g4, g5;

    seg7 u_hex0 (.code(n0), .seg(g0));
    seg7 u_hex1 (.code(n1), .seg(g1));
    seg7 u_hex2 (.code(n2), .seg(g2));
    seg7 u_hex3 (.code(n3), .seg(g3));
    seg7 u_hex4 (.code(s4), .seg(g4));
    seg7 u_hex5 (.code(s5), .seg(g5));

    // Decimal points are active low. Only HEX2's is used (SS.cc).
    assign hex0 = {1'b1, g0};
    assign hex1 = {1'b1, g1};
    assign hex2 = {(num_mode != N_SS_CC), g2};
    assign hex3 = {1'b1, g3};
    assign hex4 = {1'b1, g4};
    assign hex5 = {1'b1, g5};

endmodule
