{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
<div class="block_newsletter ciocia-newsletter" id="blockEmailSubscription_{$hookName}">
  <p class="ciocia-newsletter-title" id="block-newsletter-label">Nowości i promocje na e-mail</p>
  <form action="{$urls.current_url}#blockEmailSubscription_{$hookName}" method="post">
    <div class="ciocia-newsletter-row">
      <input name="email" type="email" value="{$value}" autocomplete="email" required
             placeholder="{l s='Your email address' d='Shop.Forms.Labels'}" aria-labelledby="block-newsletter-label">
      <input class="btn btn-primary" name="submitNewsletter" type="submit" value="Subskrybuj">
    </div>
    <input type="hidden" name="blockHookName" value="{$hookName}">
    <input type="hidden" name="action" value="0">
    {* NW_CONDITIONS, set by shop/scripts/setup/shop-content.php; registration shows the same text *}
    {if $conditions}
      <p class="ciocia-newsletter-note">{$conditions}</p>
    {/if}
    {if $msg}
      <p class="alert {if $nw_error}alert-danger{else}alert-success{/if}" role="status">{$msg}</p>
    {/if}
    {hook h='displayNewsletterRegistration'}
    {if isset($id_module)}
      {hook h='displayGDPRConsent' id_module=$id_module}
    {/if}
  </form>
</div>
