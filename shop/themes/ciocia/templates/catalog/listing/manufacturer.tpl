{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Brand page as on the source (issue #107, e.g. /brand/3-himalaya): the product list of
 * catalog/listing/product-list.tpl under a header with the brand's title and its description (an
 * introduction, sections with headings and lists, and an FAQ). The title is the brand's meta title and the
 * description is the brand's HTML description, both set by the importer (see the issue for scraping the
 * brand pages). Without them the header shows the brand's name only. The description shows on the first
 * page only, as the category description does.
 * The FAQ is a list of <details><summary>question</summary>answer</details>; the CSS draws it as an accordion.
 *}
{extends file='catalog/listing/product-list.tpl'}

{block name='product_list_header'}
  <div id="js-product-list-header" class="ciocia-listing__header ciocia-brand">
    <h1 class="ciocia-listing__title">{if $manufacturer.meta_title}{$manufacturer.meta_title}{else}{$manufacturer.name}{/if}</h1>

    {if $listing.pagination.items_shown_from == 1 && $manufacturer.description}
      <div id="manufacturer-description" class="ciocia-brand__text">{$manufacturer.description nofilter}</div>
    {/if}
  </div>
{/block}
