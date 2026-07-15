module gray_codec #(
    parameter int WIDTH = 8
) (
    input  logic [WIDTH-1:0] binary_i,
    output logic [WIDTH-1:0] gray_o,
    output logic [WIDTH-1:0] binary_o
);
    always_comb begin
        gray_o = binary_i ^ (binary_i >> 1);
        binary_o[WIDTH-1] = gray_o[WIDTH-1];
        for (int index = WIDTH-2; index >= 0; index--)
            binary_o[index] = binary_o[index+1] ^ gray_o[index];
    end
endmodule
