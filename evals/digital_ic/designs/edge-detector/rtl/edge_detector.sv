module edge_detector (
    input  logic clk,
    input  logic rst_n,
    input  logic signal_i,
    output logic pulse_o
);
    logic previous;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            previous <= 1'b0;
            pulse_o <= 1'b0;
        end else begin
            pulse_o <= signal_i && !previous;
            previous <= signal_i;
        end
    end
endmodule
