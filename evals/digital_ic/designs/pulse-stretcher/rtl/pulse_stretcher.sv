module pulse_stretcher #(
    parameter int LENGTH = 4
) (
    input  logic clk,
    input  logic rst_n,
    input  logic trigger,
    output logic pulse
);
    localparam int COUNT_WIDTH = $clog2(LENGTH + 1);
    logic [COUNT_WIDTH-1:0] remaining;
    assign pulse = (remaining != '0);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            remaining <= '0;
        else if (trigger)
            remaining <= COUNT_WIDTH'(LENGTH);
        else if (remaining != '0)
            remaining <= remaining - 1'b1;
    end
endmodule
