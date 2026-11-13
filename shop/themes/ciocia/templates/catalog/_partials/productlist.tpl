{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * The grid of product cards, used by every list: category, search, home page sections (ps_featuredproducts,
 * ps_newproducts, ps_specials, ps_bestsellers) and the lists on the product page (issue #75).
 * The columns come from custom.css, as on the source: 2 on phones, 3 from 576 px, 4 from 992 px, so the
 * Bootstrap column classes that these modules pass (productClass, cssClass="row") are not used.
 *}
<div class="products ciocia-products">
  {foreach from=$products item="product" key="position"}
    {include file="catalog/_partials/miniatures/product.tpl" product=$product position=$position}
  {/foreach}
</div>
