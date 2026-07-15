module skid_buffer #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             s_valid,
    output logic             s_ready,
    input  logic [WIDTH-1:0] s_data,
    output logic             m_valid,
    input  logic             m_ready,
    output logic [WIDTH-1:0] m_data
);
    logic full;
    logic [WIDTH-1:0] stored_data;
    assign s_ready = !full || m_ready;
    assign m_valid = full;
    assign m_data = stored_data;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            full <= 1'b0;
            stored_data <= '0;
        end else if (s_ready) begin
            full <= s_valid;
            if (s_valid)
                stored_data <= s_data;
        end
    end
endmodule
