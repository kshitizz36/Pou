// In your supabase client file
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = "https://qxsudjvfylplnkmwzvkw.supabase.co";
const supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF4c3VkanZmeWxwbG5rbXd6dmt3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MTQ1NTUyNiwiZXhwIjoyMDU3MDMxNTI2fQ.hH7-RjtCRYAg0elStW0Fr-Pd9cSx_ceTv8KGP1UR6LM";

export const supabase = createClient(supabaseUrl, supabaseKey);