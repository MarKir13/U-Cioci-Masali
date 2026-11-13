{**
 * Classic head with viewport-fit=cover, so env(safe-area-inset-bottom) keeps the bottom bar
 * above the iPhone home indicator.
 *}
{extends file='parent:_partials/head.tpl'}

{block name='head_viewport'}
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{/block}
