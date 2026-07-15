module saturating_counter #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             enable,
    input  logic             up,
    output logic [WIDTH-1:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= '0;
        else if (enable && up && count != {WIDTH{1'b1}})
            count <= count + 1'b1;
        else if (enable && !up && count != '0)
            count <= count - 1'b1;
    end
endmodule
