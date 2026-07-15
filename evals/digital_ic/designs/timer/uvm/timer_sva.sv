module timer_sva (
    input logic clk,
    input logic rst_n,
    input logic [15:0] period,
    input logic expired
);
    property reset_clears_expiry;
        @(posedge clk) !rst_n |=> !expired;
    endproperty

    property expiry_is_single_cycle;
        @(posedge clk) disable iff (!rst_n)
            expired && ($past(period) > 1) |=> !expired;
    endproperty

    assert property (reset_clears_expiry)
        else $display("TIMER_SVA_FAIL reset_clears_expiry");
    assert property (expiry_is_single_cycle)
        else $display("TIMER_SVA_FAIL expiry_is_single_cycle");
endmodule
