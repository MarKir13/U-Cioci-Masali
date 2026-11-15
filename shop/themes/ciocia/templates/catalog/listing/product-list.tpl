{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Every product list (category, search results, new products, prices drop, best sales, brand, supplier)
 * as on the source (issue #75): the title, then the count and sorting, the products in a grid and the
 * pagination, all on the page card, with no side column.
 * Classic shows category, new products, prices drop and best sales with a left column (category tree and
 * filters), set per page in the theme. The source has none, so the full-width layout is fixed here, in the
 * template, instead of through a back office setting that would only apply to new installs.
 * Kept for Classic's listing script (themes/classic/_dev/js/listing.js), which swaps these parts after
 * sorting or changing the page without a reload: #js-product-list-header, #js-product-list-top,
 * #js-product-list, #js-product-list-bottom and the .js-search-link links.
 *}
{extends file='layouts/layout-full-width.tpl'}

{block name='head_microdata_special'}
  {include file='_partials/microdata/product-list-jsonld.tpl' listing=$listing}
{/block}

{block name='content'}
  <section id="main" class="ciocia-listing">

    {block name='product_list_header'}
      <div id="js-product-list-header" class="ciocia-listing__header">
        <h1 class="ciocia-listing__title">{$listing.label}</h1>
      </div>
    {/block}

    {* Subcategories are part of the category header (catalog/_partials/category-header.tpl). *}
    {block name='subcategory_list'}{/block}

    {hook h="displayHeaderCategory"}

    <section id="products" class="ciocia-listing__products">
      {if $listing.products|count}

        {block name='product_list_top'}
          {include file='catalog/_partials/products-top.tpl' listing=$listing}
        {/block}

        {block name='product_list_active_filters'}
          {$listing.rendered_active_filters nofilter}
        {/block}

        {block name='product_list'}
          {include file='catalog/_partials/products.tpl' listing=$listing}
        {/block}

        {block name='product_list_bottom'}
          {include file='catalog/_partials/products-bottom.tpl' listing=$listing}
        {/block}

      {else}
        <div id="js-product-list-top"></div>

        <div id="js-product-list">
          {capture assign="errorContent"}
            {block name='error_content'}
              <h2 class="h4">{l s='No products available yet' d='Shop.Theme.Catalog'}</h2>
              <p>{l s='Stay tuned! More products will be shown here as they are added.' d='Shop.Theme.Catalog'}</p>
            {/block}
          {/capture}

          {include file='errors/not-found.tpl' errorContent=$errorContent}
        </div>

        <div id="js-product-list-bottom"></div>
      {/if}
    </section>

    {block name='product_list_footer'}{/block}

    {hook h="displayFooterCategory"}

  </section>
{/block}
