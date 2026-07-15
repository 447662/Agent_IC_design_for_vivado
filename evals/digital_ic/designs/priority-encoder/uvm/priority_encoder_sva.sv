module priority_encoder_sva (
    input logic clk,
    input logic [7:0] req,
    input logic [2:0] index,
    input logic valid
);
    property valid_matches_request;
        @(posedge clk) valid == (|req);
    endproperty
    property index_points_to_request;
        @(posedge clk) valid |-> req[index];
    endproperty
    assert property (valid_matches_request)
        else $display("PRIORITY_ENCODER_SVA_FAIL valid_matches_request");
    assert property (index_points_to_request)
        else $display("PRIORITY_ENCODER_SVA_FAIL index_points_to_request");
endmodule
