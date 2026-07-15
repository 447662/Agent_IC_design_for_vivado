module apb_reg_sva (
    input logic PCLK,
    input logic PRESETn,
    input logic PSEL,
    input logic PENABLE,
    input logic [7:0] PADDR,
    input logic PREADY,
    input logic PSLVERR
);
    property access_is_ready;
        @(posedge PCLK) disable iff (!PRESETn) PSEL && PENABLE |-> PREADY;
    endproperty
    property unmapped_access_errors;
        @(posedge PCLK) disable iff (!PRESETn)
            PSEL && PENABLE && (PADDR != 8'h00) && (PADDR != 8'h04) |-> PSLVERR;
    endproperty
    assert property (access_is_ready)
        else $display("APB_REG_SVA_FAIL access_is_ready");
    assert property (unmapped_access_errors)
        else $display("APB_REG_SVA_FAIL unmapped_access_errors");
endmodule
