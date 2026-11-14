{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Product card in every product list (issue #75), as on the source: a white card with the photo, one corner
 * ribbon (the discount, or "Nowy"), the name cut to three lines, "Indeks", the price with the old price,
 * a line for the lowest price before a promotion (Omnibus, D3), "Obecnie brak na stanie" and a button at
 * the bottom: "Dodaj do koszyka", or "Zobacz szczegóły" when the product cannot go to the cart from a
 * list (out of stock, or it has to be chosen in a variant first).
 *
 * The photo is the home_default thumbnail (250 px, set by Classic's theme.yml), with medium_default (452 px)
 * for screens with more pixels per point, never the 1440 px original; width, height and lazy loading are set.
 *
 * Kept for other code:
 * - .js-product-miniature with data-id-product: Classic's scripts and blockwishlist, which puts its heart
 *   button into .thumbnail-container;
 * - a.product-thumbnail: the E2E tests open a product through it (tests/support/temp-cart.js).
 * The cart button deliberately has no data-button-action="add-to-cart": the E2E tests click
 * button[data-button-action="add-to-cart"] on the product page, where ps_categoryproducts also shows cards.
 * custom.js sends this form without a reload and opens the same cart window; without JavaScript the form
 * is posted and the cart page opens.
 *
 * Omnibus (D3): modules hooked on displayProductPriceBlock with type "after_price" print into
 * .ciocia-card__price-note under the price (the line is left out while nothing prints there); the card
 * grows, the other cards in its row grow with it and the buttons stay level at the bottom.
 *}
{block name='product_miniature_item'}
{$ciocia_ribbon = null}
{$ciocia_out_of_stock = $product.availability == 'unavailable'}
{foreach from=$product.flags item=flag}
  {if $flag.type == 'discount' || $flag.type == 'on-sale'}
    {if !$ciocia_ribbon || $ciocia_ribbon.type == 'new'}{$ciocia_ribbon = $flag}{/if}
  {elseif $flag.type == 'new'}
    {if !$ciocia_ribbon}{$ciocia_ribbon = $flag}{/if}
  {elseif $flag.type == 'out_of_stock'}
    {$ciocia_out_of_stock = true}
  {/if}
{/foreach}
{if $product.cover}
  {$ciocia_image = $product.cover.bySize.home_default}
  {$ciocia_image_2x = null}
  {if !empty($product.cover.bySize.medium_default)}{$ciocia_image_2x = $product.cover.bySize.medium_default}{/if}
  {if !empty($product.cover.legend)}{$ciocia_alt = $product.cover.legend}{else}{$ciocia_alt = $product.name}{/if}
{else}
  {$ciocia_image = $urls.no_picture_image.bySize.home_default}
  {$ciocia_image_2x = null}
  {if !empty($urls.no_picture_image.bySize.medium_default)}{$ciocia_image_2x = $urls.no_picture_image.bySize.medium_default}{/if}
  {$ciocia_alt = $product.name}
{/if}
{$ciocia_sizes = '(min-width: 992px) 220px, (min-width: 576px) 210px, calc(50vw - 35px)'}
<div class="js-product product ciocia-product">
  <article class="product-miniature js-product-miniature ciocia-card" data-id-product="{$product.id_product}" data-id-product-attribute="{$product.id_product_attribute}">
    <div class="ciocia-card__media thumbnail-container">
      {block name='product_thumbnail'}
        <a href="{$product.url}" class="thumbnail product-thumbnail ciocia-card__image-link">
          <picture>
            {foreach from=['avif', 'webp'] item=ciocia_format}
              {if !empty($ciocia_image.sources[$ciocia_format])}
                <source type="image/{$ciocia_format}" srcset="{$ciocia_image.sources[$ciocia_format]} {$ciocia_image.width}w{if !empty($ciocia_image_2x.sources[$ciocia_format])}, {$ciocia_image_2x.sources[$ciocia_format]} {$ciocia_image_2x.width}w{/if}" sizes="{$ciocia_sizes}">
              {/if}
            {/foreach}
            <img
              class="ciocia-card__image"
              src="{$ciocia_image.url}"
              {if !empty($ciocia_image_2x.url)}srcset="{$ciocia_image.url} {$ciocia_image.width}w, {$ciocia_image_2x.url} {$ciocia_image_2x.width}w" sizes="{$ciocia_sizes}"{/if}
              width="{$ciocia_image.width}"
              height="{$ciocia_image.height}"
              alt="{$ciocia_alt}"
              loading="lazy"
              decoding="async"
            >
          </picture>
        </a>
      {/block}

      {block name='product_flags'}
        {if $ciocia_ribbon}
          <p class="ciocia-card__ribbon ciocia-card__ribbon--{$ciocia_ribbon.type}">{$ciocia_ribbon.label}</p>
        {/if}
      {/block}
    </div>

    <div class="ciocia-card__body">
      {block name='product_name'}
        {if $page.page_name == 'index' || $page.page_name == 'product'}
          <h3 class="ciocia-card__title"><a href="{$product.url}">{$product.name}</a></h3>
        {else}
          <h2 class="ciocia-card__title"><a href="{$product.url}">{$product.name}</a></h2>
        {/if}
      {/block}

      {if !empty($product.reference)}
        <p class="ciocia-card__reference">Indeks: {$product.reference}</p>
      {/if}

      {block name='product_price_and_shipping'}
        {if $product.show_price}
          <div class="ciocia-card__prices">
            <div class="ciocia-card__price-row">
              {hook h='displayProductPriceBlock' product=$product type="before_price"}
              <span class="ciocia-card__price">
                {if $product.has_discount}<span class="sr-only">Cena promocyjna:</span>{/if}
                {capture name='custom_price'}{hook h='displayProductPriceBlock' product=$product type='custom_price' hook_origin='products_list'}{/capture}
                {if '' !== $smarty.capture.custom_price}
                  {$smarty.capture.custom_price nofilter}
                {else}
                  {$product.price}
                {/if}
              </span>
              {if $product.has_discount}
                {hook h='displayProductPriceBlock' product=$product type="old_price"}
                <s class="ciocia-card__regular-price"><span class="sr-only">Cena regularna:</span> {$product.regular_price}</s>
              {/if}
            </div>
            {capture name='ciocia_price_note'}
              {hook h='displayProductPriceBlock' product=$product type='after_price' hook_origin='products_list'}
              {hook h='displayProductPriceBlock' product=$product type='unit_price'}
              {hook h='displayProductPriceBlock' product=$product type='weight'}
            {/capture}
            {if $smarty.capture.ciocia_price_note|strip:'' != ''}
              <div class="ciocia-card__price-note">{$smarty.capture.ciocia_price_note nofilter}</div>
            {/if}
          </div>
        {/if}
      {/block}

      {block name='product_availability'}
        {if $ciocia_out_of_stock}
          <p class="ciocia-card__availability">Obecnie brak na stanie</p>
        {/if}
      {/block}

      {block name='product_reviews'}
        {hook h='displayProductListReviews' product=$product}
      {/block}

      {block name='product_buy'}
        <div class="ciocia-card__actions">
          {if $product.add_to_cart_url && !$configuration.is_catalog}
            <form class="ciocia-card__cart js-ciocia-add-to-cart" action="{$urls.pages.cart}" method="post">
              <input type="hidden" name="token" value="{$static_token}">
              <input type="hidden" name="id_product" value="{$product.id_product}">
              <input type="hidden" name="id_product_attribute" value="{$product.id_product_attribute}">
              <input type="hidden" name="qty" value="{if !empty($product.minimal_quantity)}{$product.minimal_quantity}{else}1{/if}">
              <input type="hidden" name="add" value="1">
              <input type="hidden" name="action" value="update">
              <button type="submit" class="btn btn-primary ciocia-card__button" data-ciocia-add-to-cart>
                <i class="material-icons" aria-hidden="true">add_shopping_cart</i>
                <span class="sr-only">Dodaj do koszyka: {$product.name}</span>
              </button>
            </form>
          {else}
            <a class="btn btn-outline-primary ciocia-card__button" href="{$product.url}">
              Zobacz szczegóły<span class="sr-only">: {$product.name}</span>
            </a>
          {/if}
        </div>
      {/block}
    </div>
  </article>
</div>
{/block}
