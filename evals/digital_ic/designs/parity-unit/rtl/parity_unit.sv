module parity_unit #(
    parameter int WIDTH = 16
) (
    input  logic [WIDTH-1:0] data_i,
    input  logic             parity_i,
    output logic             parity_o,
    output logic             error_o
);
    always_comb begin
        parity_o = ^data_i;
        error_o = parity_o ^ parity_i;
    end
endmodule
