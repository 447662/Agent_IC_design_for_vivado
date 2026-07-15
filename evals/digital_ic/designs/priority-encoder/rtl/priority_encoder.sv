module priority_encoder #(
    parameter int REQUESTS = 8,
    parameter int INDEX_WIDTH = 3
) (
    input  logic [REQUESTS-1:0]   req,
    output logic [INDEX_WIDTH-1:0] index,
    output logic                   valid
);
    always_comb begin
        index = '0;
        valid = 1'b0;
        for (int request_index = REQUESTS-1; request_index >= 0; request_index--) begin
            if (req[request_index] && !valid) begin
                index = INDEX_WIDTH'(request_index);
                valid = 1'b1;
            end
        end
    end
endmodule
