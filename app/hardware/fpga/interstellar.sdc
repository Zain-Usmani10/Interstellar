# Interstellar FPGA controller - timing constraints
# One clock: the onboard 50 MHz oscillator (20 ns period).
create_clock -name clk50 -period 20.000 [get_ports {MAX10_CLK1_50}]
derive_clock_uncertainty

# Push buttons and the UART receive line are asynchronous to clk50. They are
# synchronised inside the design, so their pin arrival time is not analysed.
set_false_path -from [get_ports {KEY[*]}]
set_false_path -from [get_ports {UART_RX}]

# LEDs and the UART transmit line are slow, human/115200-baud outputs with no
# clocked receiver that shares clk50.
set_false_path -to [get_ports {LEDR[*]}]
set_false_path -to [get_ports {UART_TX}]
