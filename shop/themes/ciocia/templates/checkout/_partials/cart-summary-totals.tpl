{**
 * Cart and checkout summary totals (issue #44): Classic's, without the "VAT (wliczony)" line, as on the
 * source. Prices are gross and the total says "(brutto)", so the line only repeated that.
 *}
{extends file='parent:checkout/_partials/cart-summary-totals.tpl'}

{block name='cart_summary_tax'}{/block}
