{**
 * Home page as on the source shop: the banner, the category tiles, "what do you need", featured products,
 * brands, guides, new products, the SEO text and "our story". Classic prints every module hooked on
 * displayHome in the order of their positions; here each section has its place.
 *
 * - The banner is ps_imageslider (modules/ps_imageslider/.../slider.tpl, issue #63).
 * - Featured and new products are Classic's modules; their markup is styled in custom.css.
 * - The static sections are the widgets of our module ciociahome (shop/modules/ciociahome).
 * ps_specials ("Wyprzedaż"), which Classic also hooks on displayHome, is not on the source's home page.
 *}
{extends file='parent:index.tpl'}

{block name='page_content'}
  <div class="ciocia-home">
    {hook h='displayHome' mod='ps_imageslider'}
    {widget name='ciociahome' section='categories'}
    {widget name='ciociahome' section='needs'}
    {widget name='ciociahome' section='featured'}
    {widget name='ciociahome' section='brands'}
    {widget name='ciociahome' section='guides'}
    {widget name='ciociahome' section='new'}
    {widget name='ciociahome' section='seo'}
    {widget name='ciociahome' section='about'}
  </div>
{/block}
