module timer #(
    parameter int WIDTH = 16
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             load,
    input  logic             enable,
    input  logic [WIDTH-1:0] period,
    output logic             expired
);
    logic [WIDTH-1:0] remaining;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            remaining <= '0;
            expired   <= 1'b0;
        end else begin
            expired <= 1'b0;
            if (load) begin
                remaining <= (period == '0) ? {{(WIDTH-1){1'b0}}, 1'b1} : period;
            end else if (enable) begin
                if (remaining <= {{(WIDTH-1){1'b0}}, 1'b1}) begin
                    expired   <= 1'b1;
                    remaining <= (period == '0) ? {{(WIDTH-1){1'b0}}, 1'b1} : period;
                end else begin
                    remaining <= remaining - 1'b1;
                end
            end
        end
    end
endmodule
