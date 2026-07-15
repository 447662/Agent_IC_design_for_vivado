module apb_register_block (
    input  logic        PCLK,
    input  logic        PRESETn,
    input  logic        PSEL,
    input  logic        PENABLE,
    input  logic        PWRITE,
    input  logic [7:0]  PADDR,
    input  logic [31:0] PWDATA,
    input  logic [3:0]  PSTRB,
    output logic [31:0] PRDATA,
    output logic        PREADY,
    output logic        PSLVERR,
    input  logic [31:0] status_i,
    output logic [31:0] control_o
);
    logic access;
    logic control_address;
    logic status_address;

    assign access = PSEL && PENABLE;
    assign control_address = (PADDR == 8'h00);
    assign status_address = (PADDR == 8'h04);
    assign PREADY = 1'b1;

    always_comb begin
        PRDATA = 32'h0000_0000;
        if (control_address)
            PRDATA = control_o;
        else if (status_address)
            PRDATA = status_i;
        PSLVERR = access && ((!control_address && !status_address) || (PWRITE && status_address));
    end

    always_ff @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            control_o <= 32'h0000_0000;
        end else if (access && PWRITE && control_address) begin
            for (int byte_index = 0; byte_index < 4; byte_index++) begin
                if (PSTRB[byte_index])
                    control_o[byte_index*8 +: 8] <= PWDATA[byte_index*8 +: 8];
            end
        end
    end
endmodule
