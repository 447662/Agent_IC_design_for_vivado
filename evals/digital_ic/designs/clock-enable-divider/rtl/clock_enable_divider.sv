module clock_enable_divider #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic [WIDTH-1:0] divisor,
    output logic             tick
);
    logic [WIDTH-1:0] count;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= '0;
            tick <= 1'b0;
        end else if (divisor <= 1) begin
            count <= '0;
            tick <= 1'b1;
        end else if (count == divisor - 1'b1) begin
            count <= '0;
            tick <= 1'b1;
        end else begin
            count <= count + 1'b1;
            tick <= 1'b0;
        end
    end
endmodule
